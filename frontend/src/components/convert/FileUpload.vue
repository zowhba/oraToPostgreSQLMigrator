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
  </div>
</template>

<script>
import { parseMyBatisXml } from '../../utils/xmlParser.js'
import { parseExcelQueries } from '../../utils/excelParser.js'
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
      sourceType: ''
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

      try {
        let namespace = ''
        let queries = []

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
          // 엑셀은 네임스페이스가 없으므로 파일명 등으로 대체하거나 비워둠
          namespace = file.name.split('.')[0]
        }

        this.$emit('file-parsed', {
          fileName: file.name,
          namespace,
          sourceType,
          queries
        })
      } catch (error) {
        alert('파일 파싱 오류: ' + error.message)
        this.clearFile()
      }
    },

    clearFile() {
      this.fileName = ''
      this.sourceType = ''
      this.$refs.fileInput.value = ''
      this.$emit('file-parsed', {
        fileName: '',
        namespace: '',
        sourceType: '',
        queries: []
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
</style>
