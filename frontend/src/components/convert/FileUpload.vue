<template>
  <div class="file-upload">
    <div
      class="upload-area"
      :class="{ 'drag-over': isDragging, disabled: disabled }"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="handleDrop"
      @click="openFileDialog"
    >
      <input
        type="file"
        ref="fileInput"
        accept=".xml,.xlsx,.xls,.sql"
        @change="handleFileSelect"
        hidden
      />

      <div class="upload-icon">&#128194;</div>
      <div class="upload-text-group">
        <p class="upload-text">
          XML · 엑셀 · SQL 파일을 드래그하거나 클릭하여 선택하세요
        </p>
        <p class="upload-hint">
          MyBatis XML (.xml) · 엑셀 (.xlsx, .xls) · SQL 스크립트 (.sql)
        </p>
      </div>
    </div>

    <!-- 선택된 파일 정보 -->
    <div class="file-info" v-if="fileName">
      <span class="file-name">{{ fileName }}</span>
      <button class="btn-remove" @click="clearFile">삭제</button>
    </div>

    <!-- .sql 소스 안내 -->
    <div class="sql-notice" v-if="sourceType === 'sql'">
      <span class="notice-icon">ℹ️</span>
      <span>
        SQL 스크립트는 <strong>Dry-run(EXPLAIN) 검증을 수행하지 않습니다.</strong>
        프로젝트에 설정된 대상 DB의 스키마는 변환 참고용으로만 사용됩니다.
      </span>
    </div>

    <!-- ────── 엑셀 인식 결과 확인/수정 ────── -->
    <div class="excel-panel" :class="{ warn: excelMeta && excelMeta.confidence === 'low' }" v-if="excelMeta">
      <div class="excel-panel-head">
        <span class="notice-icon">{{ excelMeta.confidence === 'low' ? '⚠️' : '✅' }}</span>
        <strong>엑셀 인식 결과</strong>
        <span class="excel-count">{{ excelQueryCount }}개 쿼리 추출</span>
        <span class="excel-hint" v-if="excelMeta.confidence === 'low'">
          쿼리 컬럼이 확실하지 않습니다. 아래에서 확인해 주세요.
        </span>
      </div>

      <div class="excel-controls">
        <label class="excel-field">
          <span class="excel-label">시트</span>
          <select class="excel-select" :value="excelMeta.sheetName" @change="reparse({ sheetName: $event.target.value })">
            <option v-for="name in excelMeta.sheetNames" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>

        <label class="excel-field">
          <span class="excel-label">머리글 행</span>
          <select class="excel-select" :value="String(excelMeta.headerRow)" @change="reparse({ headerRow: Number($event.target.value) })">
            <option value="-1">(머리글 없음)</option>
            <option v-for="row in headerRowOptions" :key="row" :value="String(row)">{{ row + 1 }}행</option>
          </select>
        </label>

        <label class="excel-field grow">
          <span class="excel-label">쿼리 컬럼</span>
          <select class="excel-select" :value="String(excelMeta.sqlColumn)" @change="reparse({ sqlColumn: Number($event.target.value) })">
            <option v-for="column in excelMeta.headers" :key="column.index" :value="String(column.index)">
              {{ column.letter }}열{{ column.label ? ` · ${column.label}` : '' }}
              {{ column.score > 0 ? `  (SQL 적합도 ${column.score})` : '' }}
            </option>
          </select>
        </label>
      </div>

      <div class="excel-preview" v-if="excelMeta.preview && excelMeta.preview.length">
        <div class="excel-preview-title">미리보기 (앞 {{ excelMeta.preview.length }}건)</div>
        <div class="excel-preview-item" v-for="item in excelMeta.preview" :key="item.queryId">
          <span class="preview-tag">{{ item.tagName }}</span>
          <span class="preview-id">{{ item.queryId }}</span>
          <pre class="preview-sql">{{ item.sql }}</pre>
        </div>
      </div>

      <p class="excel-foot">
        쿼리 셀이 <code>Sql = "SELECT ..."</code> 형태의 Java 코드여도 실제 SQL만 자동으로 뽑아냅니다.
        바인드 <code>?</code>는 그대로 유지되며, 결과 파일은 <strong>원본 엑셀에서 쿼리 부분만 변환</strong>되어 내려받습니다.
      </p>
    </div>
  </div>
</template>

<script>
import { markRaw } from 'vue'
import { parseMyBatisXml } from '../../utils/xmlParser.js'
import { parseExcelQueries, parseWorkbookQueries } from '../../utils/excelParser.js'
import { parseSqlScript } from '../../utils/sqlParser.js'

export default {
  name: 'FileUpload',
  props: {
    disabled: {
      type: Boolean,
      default: false
    }
  },
  emits: ['file-parsed'],
  data() {
    return {
      isDragging: false,
      fileName: '',
      sourceType: '',
      // 엑셀 인식 결과 (원본 바이트 포함 — 반응형 프록시를 피하려 markRaw 사용)
      excelMeta: null,
      excelQueryCount: 0
    }
  },
  computed: {
    /** 머리글 행 선택 후보 — 앞부분 몇 행만 노출 */
    headerRowOptions() {
      const limit = 15
      return Array.from({ length: limit }, (_, index) => index)
    }
  },
  methods: {
    openFileDialog() {
      if (!this.disabled) {
        this.$refs.fileInput.click()
      }
    },

    handleDrop(e) {
      this.isDragging = false
      if (this.disabled) return

      const files = e.dataTransfer.files
      if (files.length > 0) {
        this.processFile(files[0])
      }
    },

    handleFileSelect(e) {
      const files = e.target.files
      if (files.length > 0) {
        this.processFile(files[0])
      }
    },

    /**
     * 파일 확장자로 소스 종류를 판별합니다.
     * @returns {'xml'|'excel'|'sql'|''}
     */
    detectSourceType(fileName) {
      const name = fileName.toLowerCase()
      if (name.endsWith('.xml')) return 'xml'
      if (name.endsWith('.xlsx') || name.endsWith('.xls')) return 'excel'
      if (name.endsWith('.sql')) return 'sql'
      return ''
    },

    async processFile(file) {
      const sourceType = this.detectSourceType(file.name)

      if (!sourceType) {
        alert('XML(.xml), 엑셀(.xlsx, .xls), SQL(.sql) 파일만 업로드 가능합니다.')
        return
      }

      this.fileName = file.name
      this.sourceType = sourceType
      this.excelMeta = null
      this.excelQueryCount = 0

      try {
        let namespace = ''
        let queries = []
        let excelMeta = null

        if (sourceType === 'xml') {
          const content = await file.text()
          const parsed = parseMyBatisXml(content)
          namespace = parsed.namespace
          queries = parsed.queries
        } else if (sourceType === 'sql') {
          const content = await file.text()
          const parsed = parseSqlScript(content)
          queries = parsed.queries
          // .sql은 네임스페이스가 없으므로 파일명으로 대체
          namespace = file.name.split('.').slice(0, -1).join('.')
        } else {
          const parsed = await parseExcelQueries(file)
          queries = parsed.queries
          excelMeta = parsed.meta
          // 엑셀은 네임스페이스가 없으므로 파일명 등으로 대체하거나 비워둠
          namespace = file.name.split('.')[0]
        }

        this.applyParsed({ fileName: file.name, namespace, sourceType, queries, excelMeta })
      } catch (error) {
        alert('파일 파싱 오류: ' + error.message)
        this.clearFile()
      }
    },

    /**
     * 사용자가 [엑셀 인식 결과]에서 시트/머리글 행/쿼리 컬럼을 바꾸면
     * 보관해 둔 원본 바이트로 다시 파싱합니다.
     */
    reparse(override) {
      if (!this.excelMeta) return

      // 시트를 바꾸면 머리글 행·컬럼은 다시 자동 탐색해야 한다
      const base = override.sheetName
        ? { sheetName: override.sheetName }
        : {
            sheetName: this.excelMeta.sheetName,
            headerRow: this.excelMeta.headerRow,
            sqlColumn: this.excelMeta.sqlColumn,
            ...override
          }

      // 머리글 행만 바꾼 경우 쿼리 컬럼은 새 머리글로 다시 판단하도록 비운다
      if (override.headerRow !== undefined) delete base.sqlColumn

      try {
        const { queries, meta } = parseWorkbookQueries(this.excelMeta.fileBytes, base)
        this.applyParsed({
          fileName: this.fileName,
          namespace: this.fileName.split('.')[0],
          sourceType: 'excel',
          queries,
          excelMeta: { ...meta, fileName: this.excelMeta.fileName }
        })
      } catch (error) {
        alert('엑셀 재파싱 오류: ' + error.message)
      }
    },

    applyParsed({ fileName, namespace, sourceType, queries, excelMeta }) {
      this.excelMeta = excelMeta ? markRaw(excelMeta) : null
      this.excelQueryCount = queries.length

      this.$emit('file-parsed', {
        fileName,
        namespace,
        sourceType,
        queries,
        excelMeta: this.excelMeta
      })
    },

    clearFile() {
      this.fileName = ''
      this.sourceType = ''
      this.excelMeta = null
      this.excelQueryCount = 0
      this.$refs.fileInput.value = ''
      this.$emit('file-parsed', {
        fileName: '',
        namespace: '',
        sourceType: '',
        queries: [],
        excelMeta: null
      })
    }
  }
}
</script>

<style scoped>
.file-upload {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upload-area {
  border: 2px dashed #ccc;
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
  display: flex;
  align-items: center;
  gap: 14px;
}

.upload-area:hover {
  border-color: #667eea;
  background: #f0f4ff;
}

.upload-area.drag-over {
  border-color: #667eea;
  background: #e8edff;
}

.upload-area.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.upload-icon {
  font-size: 24px;
  line-height: 1;
}

.upload-text-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.upload-text {
  font-size: 13px;
  color: #333;
  margin: 0;
}

.upload-hint {
  font-size: 11px;
  color: #888;
  margin: 0;
}

.file-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #e8f5e9;
  border-radius: 6px;
}

.file-name {
  font-size: 13px;
  color: #2e7d32;
  font-weight: 500;
}

.btn-remove {
  padding: 3px 10px;
  background: #ffebee;
  color: #c62828;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.btn-remove:hover {
  background: #ffcdd2;
}

.sql-notice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: #eef4ff;
  border: 1px solid #c7d8ff;
  border-radius: 6px;
  font-size: 12px;
  color: #33478a;
  line-height: 1.6;
}

.sql-notice .notice-icon {
  flex-shrink: 0;
}

.sql-notice strong {
  color: #1e3a8a;
}

/* ── 엑셀 인식 결과 패널 ── */
.excel-panel {
  border: 1px solid #c7d8ff;
  background: #f8fbff;
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.excel-panel.warn {
  border-color: #ffd08a;
  background: #fffaf0;
}

.excel-panel-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
  color: #1e3a8a;
}

.excel-panel.warn .excel-panel-head {
  color: #92400e;
}

.excel-count {
  padding: 2px 8px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #c7d8ff;
  font-size: 11.5px;
  font-weight: 600;
}

.excel-hint {
  font-size: 12px;
  font-weight: 500;
}

.excel-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.excel-field {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.excel-field.grow {
  flex: 1;
  min-width: 260px;
}

.excel-label {
  font-size: 12px;
  color: #475569;
  white-space: nowrap;
}

.excel-select {
  flex: 1;
  min-width: 0;
  padding: 5px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 12.5px;
  background: #fff;
  cursor: pointer;
}

.excel-select:focus {
  outline: none;
  border-color: #667eea;
}

.excel-preview {
  border-top: 1px dashed #c7d8ff;
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.excel-preview-title {
  font-size: 11.5px;
  font-weight: 600;
  color: #64748b;
}

.excel-preview-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
}

.preview-tag {
  flex-shrink: 0;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e3f2fd;
  color: #1976d2;
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
}

.preview-id {
  flex-shrink: 0;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Fira Code', monospace;
  color: #334155;
}

.preview-sql {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 4px 8px;
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 11px;
  line-height: 1.5;
  max-height: 48px;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-all;
}

.excel-foot {
  margin: 0;
  font-size: 11.5px;
  color: #64748b;
  line-height: 1.7;
}

.excel-foot code {
  padding: 1px 5px;
  background: #eef2ff;
  border-radius: 3px;
  font-family: 'Fira Code', monospace;
  font-size: 11px;
  color: #4338ca;
}
</style>
