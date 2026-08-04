#!/usr/bin/env bash
#
# AQMS (AI Query Migration System) — 운영 배포 스크립트
#
#   ./deploy.sh              최신 소스로 이미지 빌드 후 컨테이너 재기동 (기본)
#   ./deploy.sh --pull       git pull 후 배포
#   ./deploy.sh status       컨테이너 상태 확인 (포트 점유 현황 포함)
#   ./deploy.sh logs         로그 실시간 확인 (Ctrl+C로 빠져나옴)
#   ./deploy.sh restart      재시작 (.env 변경분은 반영되지 않음 → deploy 사용)
#   ./deploy.sh stop         중지 및 컨테이너 삭제
#   ./deploy.sh rollback     직전 이미지로 되돌리기
#
#   옵션:
#     --force, -f            포트를 점유한 컨테이너/프로세스를 확인 없이 정리
#     --pull                 배포 전 git pull 수행
#
# 컨테이너는 --restart unless-stopped 로 기동되므로
# 터미널을 닫거나 서버가 재부팅되어도 자동으로 다시 올라옵니다.
#
set -euo pipefail

# ── 설정 (환경변수로 덮어쓸 수 있음) ─────────────────────
APP_NAME="${APP_NAME:-aqms}"
IMAGE="${IMAGE:-aqms}"
PORT="${PORT:-80}"
ENV_FILE="${ENV_FILE:-.env}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
FORCE="${FORCE:-0}"        # 1이면 포트 점유 대상을 확인 없이 정리

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 출력 헬퍼 ────────────────────────────────────────────
if [ -t 1 ]; then
  C_INFO=$'\033[0;36m'; C_OK=$'\033[0;32m'; C_WARN=$'\033[0;33m'
  C_ERR=$'\033[0;31m';  C_OFF=$'\033[0m'
else
  C_INFO=""; C_OK=""; C_WARN=""; C_ERR=""; C_OFF=""
fi

info() { echo "${C_INFO}▶${C_OFF} $*"; }
ok()   { echo "${C_OK}✅${C_OFF} $*"; }
warn() { echo "${C_WARN}⚠️ ${C_OFF} $*"; }
die()  { echo "${C_ERR}❌ $*${C_OFF}" >&2; exit 1; }

# ── docker 실행 방식 결정 (sudo 필요 여부 자동 판별) ─────
DOCKER=""

ensure_docker() {
  [ -n "$DOCKER" ] && return 0

  command -v docker >/dev/null 2>&1 || die "docker가 설치되어 있지 않습니다."

  if docker info >/dev/null 2>&1; then
    DOCKER="docker"
  elif sudo docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
    warn "docker 소켓 권한이 없어 sudo로 실행합니다."
    warn "   sudo usermod -aG docker \$USER  실행 후 재로그인하면 sudo 없이 쓸 수 있습니다."
  else
    die "docker 데몬에 접속할 수 없습니다. 'sudo systemctl enable --now docker' 를 먼저 실행하세요."
  fi
}

container_exists() { $DOCKER ps -aq -f "name=^${APP_NAME}$" | grep -q .; }
container_running() { $DOCKER ps -q -f "name=^${APP_NAME}$" | grep -q .; }

# ── 포트 점유 확인 및 정리 ───────────────────────────────

# 해당 포트를 LISTEN 중인 호스트 PID 목록
port_listener_pids() {
  if command -v ss >/dev/null 2>&1; then
    sudo ss -lntpH "sport = :${PORT}" 2>/dev/null \
      | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u
  elif command -v lsof >/dev/null 2>&1; then
    sudo lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null | sort -u
  fi
}

port_in_use() {
  if command -v ss >/dev/null 2>&1; then
    ss -lntH "sport = :${PORT}" 2>/dev/null | grep -q .
  elif command -v lsof >/dev/null 2>&1; then
    sudo lsof -ti "tcp:${PORT}" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1   # 확인 수단이 없으면 점유되지 않은 것으로 간주하고 진행
  fi
}

# 해당 포트를 게시(publish)하고 있는 다른 컨테이너 ID 목록
conflicting_containers() {
  $DOCKER ps -q --filter "publish=${PORT}" 2>/dev/null \
    | while read -r cid; do
        [ -n "$cid" ] || continue
        # 우리 컨테이너는 제외 (어차피 배포 직전에 제거됨)
        name="$($DOCKER inspect -f '{{.Name}}' "$cid" 2>/dev/null | sed 's|^/||')"
        [ "$name" = "$APP_NAME" ] || echo "$cid"
      done
}

confirm() {
  local prompt="$1"

  if [ "$FORCE" = "1" ]; then
    return 0
  fi

  if [ ! -t 0 ]; then
    die "대화형 터미널이 아니므로 확인을 받을 수 없습니다. --force 옵션을 사용하세요."
  fi

  local answer
  read -r -p "${prompt} [y/N] " answer
  case "$answer" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

# 포트를 점유한 컨테이너/프로세스를 정리한다.
free_port() {
  port_in_use || return 0

  echo
  warn "포트 ${PORT}이(가) 이미 사용 중입니다."

  # ── 1) 다른 도커 컨테이너가 잡고 있는 경우 ──
  local cids
  cids="$(conflicting_containers || true)"

  if [ -n "$cids" ]; then
    echo
    echo "  ── 포트 ${PORT}을 사용 중인 컨테이너 ──"
    for cid in $cids; do
      $DOCKER ps --filter "id=${cid}" \
        --format '  {{.Names}}  ({{.Image}})  {{.Status}}  {{.Ports}}' 2>/dev/null \
        || echo "  $cid"
    done
    echo

    if confirm "위 컨테이너를 중지하고 계속할까요?"; then
      for cid in $cids; do
        local cname
        cname="$($DOCKER inspect -f '{{.Name}}' "$cid" 2>/dev/null | sed 's|^/||')"
        info "컨테이너 중지: ${cname:-$cid}"
        # --restart 정책 때문에 되살아나지 않도록 정책을 먼저 해제
        $DOCKER update --restart=no "$cid" >/dev/null 2>&1 || true
        $DOCKER stop "$cid" >/dev/null 2>&1 || true
      done
      ok "충돌 컨테이너 중지 완료"
    else
      die "배포를 중단했습니다. (PORT=8080 ./deploy.sh 처럼 다른 포트를 쓸 수도 있습니다)"
    fi
  fi

  # ── 2) 여전히 점유 중이면 호스트 프로세스 ──
  sleep 1
  port_in_use || return 0

  local pids
  pids="$(port_listener_pids || true)"

  if [ -z "$pids" ]; then
    die "포트 ${PORT}이 사용 중이지만 점유 프로세스를 확인하지 못했습니다. 'sudo ss -lntp | grep :${PORT}' 로 직접 확인해 주세요."
  fi

  echo
  echo "  ── 포트 ${PORT}을 사용 중인 호스트 프로세스 ──"
  for pid in $pids; do
    printf '  PID %-8s %s\n' "$pid" "$(ps -p "$pid" -o args= 2>/dev/null | cut -c1-100)"
  done
  echo
  warn "도커 컨테이너가 아닌 서버의 프로세스입니다. (예: 호스트에 설치된 nginx/httpd)"
  warn "   systemd 서비스라면 'sudo systemctl disable --now nginx' 처럼 정식으로 내리는 편이 안전합니다."
  echo

  if confirm "위 프로세스를 종료하고 계속할까요?"; then
    for pid in $pids; do
      info "프로세스 종료: PID ${pid}"
      sudo kill "$pid" 2>/dev/null || true
    done

    # 최대 10초 대기 후 강제 종료
    local waited=0
    while port_in_use && [ "$waited" -lt 10 ]; do
      sleep 1
      waited=$((waited + 1))
    done

    if port_in_use; then
      warn "정상 종료되지 않아 강제 종료합니다."
      for pid in $pids; do
        sudo kill -9 "$pid" 2>/dev/null || true
      done
      sleep 2
    fi

    if port_in_use; then
      die "포트 ${PORT}을 확보하지 못했습니다."
    fi
    ok "포트 ${PORT} 확보 완료"
  else
    die "배포를 중단했습니다. (PORT=8080 ./deploy.sh 처럼 다른 포트를 쓸 수도 있습니다)"
  fi
}

# ── 컨테이너 기동 ────────────────────────────────────────
run_container() {
  local tag="$1"

  info "컨테이너 기동 중... (${IMAGE}:${tag} → 포트 ${PORT})"
  if ! $DOCKER run -d \
    --name "$APP_NAME" \
    --restart unless-stopped \
    -p "${PORT}:80" \
    --env-file "$ENV_FILE" \
    -e TZ=Asia/Seoul \
    --health-cmd "wget -q -O /dev/null http://127.0.0.1:8000/health || exit 1" \
    --health-interval 30s \
    --health-timeout 5s \
    --health-retries 3 \
    "${IMAGE}:${tag}" >/dev/null
  then
    # 기동 실패 시 생성만 된 컨테이너가 남지 않도록 정리
    $DOCKER rm -f "$APP_NAME" >/dev/null 2>&1 || true
    die "컨테이너 기동에 실패했습니다."
  fi
}

remove_container() {
  if container_exists; then
    info "기존 컨테이너 제거 중..."
    $DOCKER rm -f "$APP_NAME" >/dev/null
  fi
}

# ── 헬스체크 대기 ────────────────────────────────────────
wait_for_health() {
  info "기동 확인 중... (최대 ${HEALTH_TIMEOUT}초)"

  local elapsed=0
  while [ "$elapsed" -lt "$HEALTH_TIMEOUT" ]; do
    if ! container_running; then
      echo
      warn "컨테이너가 종료되었습니다. 최근 로그:"
      $DOCKER logs --tail 40 "$APP_NAME" 2>&1 || true
      die "기동 실패"
    fi

    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      echo
      return 0
    fi

    printf '.'
    sleep 2
    elapsed=$((elapsed + 2))
  done

  echo
  warn "헬스체크 응답이 없습니다. 최근 로그:"
  $DOCKER logs --tail 40 "$APP_NAME" 2>&1 || true
  die "기동 확인 실패 (컨테이너는 살아 있을 수 있으니 './deploy.sh logs' 로 확인하세요)"
}

print_endpoint() {
  local host
  host="$(curl -fsS --max-time 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
  if [ -n "$host" ]; then
    ok "접속 주소: http://${host}$([ "$PORT" = "80" ] || echo ":${PORT}")"
  else
    ok "접속 주소: http://<서버주소>$([ "$PORT" = "80" ] || echo ":${PORT}")"
  fi
}

# ── 명령: 배포 ───────────────────────────────────────────
cmd_deploy() {
  local do_pull="${1:-no}"

  [ -f "$ENV_FILE" ] || die "${ENV_FILE} 파일이 없습니다. .env.example을 복사해 값을 채워주세요."
  [ -f Dockerfile ] || die "Dockerfile을 찾을 수 없습니다. (현재 위치: ${SCRIPT_DIR})"

  echo "════════════════════════════════════════════"
  echo " AQMS 배포  —  $(date '+%Y-%m-%d %H:%M:%S')"
  echo "════════════════════════════════════════════"

  if [ "$do_pull" = "pull" ]; then
    info "git pull 중..."
    git pull --ff-only
  fi

  # 롤백용으로 직전 이미지 보관
  if $DOCKER image inspect "${IMAGE}:latest" >/dev/null 2>&1; then
    $DOCKER tag "${IMAGE}:latest" "${IMAGE}:previous"
    info "직전 이미지를 ${IMAGE}:previous 로 보관했습니다."
  fi

  info "이미지 빌드 중... (수 분 소요될 수 있습니다)"
  $DOCKER build -t "${IMAGE}:latest" .

  remove_container
  free_port
  run_container latest
  wait_for_health

  ok "배포 완료"
  print_endpoint
  echo "   로그: ./deploy.sh logs   |   상태: ./deploy.sh status"

  # dangling 이미지 정리
  $DOCKER image prune -f >/dev/null 2>&1 || true
}

# ── 명령: 롤백 ───────────────────────────────────────────
cmd_rollback() {
  $DOCKER image inspect "${IMAGE}:previous" >/dev/null 2>&1 \
    || die "롤백할 이전 이미지(${IMAGE}:previous)가 없습니다."

  info "직전 이미지로 롤백합니다."
  remove_container
  free_port
  run_container previous
  wait_for_health
  ok "롤백 완료"
  print_endpoint
}

# ── 명령: 상태 / 로그 / 제어 ─────────────────────────────
cmd_status() {
  if container_exists; then
    $DOCKER ps -a --filter "name=^${APP_NAME}$" \
      --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'
    echo
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      ok "헬스체크 정상 (http://127.0.0.1:${PORT}/health)"
    else
      warn "헬스체크 응답 없음"
    fi
  else
    warn "컨테이너 '${APP_NAME}'가 없습니다. './deploy.sh' 로 배포하세요."
  fi

  # 포트 점유 현황
  echo
  echo "  ── 포트 ${PORT} 점유 현황 ──"
  if command -v ss >/dev/null 2>&1; then
    { sudo ss -lntp "sport = :${PORT}" 2>/dev/null || ss -lnt "sport = :${PORT}" 2>/dev/null; } \
      | sed 's/^/  /' || true
  else
    echo "  (ss 명령이 없어 확인할 수 없습니다)"
  fi
}

cmd_logs() {
  container_exists || die "컨테이너 '${APP_NAME}'가 없습니다."
  $DOCKER logs -f --tail 100 "$APP_NAME"
}

cmd_restart() {
  container_exists || die "컨테이너 '${APP_NAME}'가 없습니다. './deploy.sh' 로 배포하세요."
  info "컨테이너 재시작 중..."
  $DOCKER restart "$APP_NAME" >/dev/null
  wait_for_health
  ok "재시작 완료"
  warn ".env를 수정하셨다면 재시작으로는 반영되지 않습니다. './deploy.sh' 를 실행하세요."
}

cmd_stop() {
  container_exists || { warn "실행 중인 컨테이너가 없습니다."; return 0; }
  remove_container
  ok "중지 완료 (자동 재시작도 해제되었습니다)"
}

usage() {
  # 파일 상단의 주석 블록(shebang 제외)을 그대로 도움말로 출력
  awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
}

# ── 진입점 ───────────────────────────────────────────────
CMD=""
DO_PULL="no"

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help|help) usage; exit 0 ;;
    -f|--force)     FORCE=1 ;;
    --pull)         DO_PULL="pull" ;;
    deploy|pull|rollback|status|ps|logs|log|restart|stop|down)
      if [ "$1" = "pull" ]; then DO_PULL="pull"; fi
      if [ -z "$CMD" ]; then CMD="$1"; fi
      ;;
    *) echo "알 수 없는 인자: $1" >&2; echo >&2; usage >&2; exit 1 ;;
  esac
  shift
done

if [ -z "$CMD" ] || [ "$CMD" = "pull" ]; then CMD="deploy"; fi

ensure_docker

case "$CMD" in
  deploy)    cmd_deploy "$DO_PULL" ;;
  rollback)  cmd_rollback ;;
  status|ps) cmd_status ;;
  logs|log)  cmd_logs ;;
  restart)   cmd_restart ;;
  stop|down) cmd_stop ;;
esac
