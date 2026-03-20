import re
import streamlit as st
from xml.etree import ElementTree as ET

def debug_log(message: str) -> None:
    """디버그 로그 출력 (Streamlit 세션 상태 확인)"""
    if st.session_state.get('debug_enabled', False):
        st.info(message)

def format_xml_consistently(xml_content):
    """
    XML의 들여쓰기와 개행을 일관된 형태로 포맷팅합니다.
    """
    try:
        root = ET.fromstring(xml_content)
        
        def indent(elem, level=0):
            i = "\n" + level * "    "
            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + "    "
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
                for child in elem:
                    indent(child, level + 1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i
        
        indent(root)
        formatted_xml = ET.tostring(root, encoding='unicode')
        
        # Mybatis 태그들의 일관된 포맷팅
        formatted_xml = re.sub(r'>\s*\n\s*<', '>\n        <', formatted_xml)
        formatted_xml = re.sub(r'>\s*([^<]+)\s*<', r'>\n            \1\n        <', formatted_xml)
        
        # 특정 태그들의 포맷팅 개선
        for tag in ['select', 'insert', 'update', 'delete']:
            formatted_xml = re.sub(rf'(<{tag}[^>]*>)\s*\n', rf'\1\n        ', formatted_xml)
            formatted_xml = re.sub(rf'\n\s*(</{tag}>)', r'\n    \1', formatted_xml)
        
        return formatted_xml
        
    except Exception:
        # XML 파싱 실패 시 기본 포맷팅 적용
        formatted_xml = re.sub(r'\n\s*\n', '\n', xml_content)
        formatted_xml = re.sub(r'^\s+', '', formatted_xml, flags=re.MULTILINE)
        formatted_xml = re.sub(r'>\s+<', '>\n<', formatted_xml)
        formatted_xml = re.sub(r'>\s+([^<])', r'>\n        \1', formatted_xml)
        formatted_xml = re.sub(r'([^>])\s+<', r'\1\n        <', formatted_xml)
        return formatted_xml

def extract_pure_sql_from_xml(xml_content):
    """
    Mybatis XML에서 순수 SQL을 추출합니다.
    """
    try:
        # CDATA 섹션 제거
        sql_content = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', xml_content, flags=re.DOTALL)
        
        # Mybatis 파라미터 치환
        sql_content = re.sub(r'#\{([^}]+)\}', r':\1', sql_content)  # PostgreSQL style
        sql_content = re.sub(r'\$\{([^}]+)\}', r':\1', sql_content)
        
        # Mybatis 동적 태그 제거 (단순 추출용)
        for tag in ['if', 'choose', 'when', 'otherwise', 'foreach', 'where', 'set', 'trim']:
            sql_content = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', sql_content, flags=re.DOTALL)
        
        # XML 태그 제거
        sql_content = re.sub(r'<[^>]+>', '', sql_content)
        
        # 공백 정리
        sql_content = re.sub(r'\s+', ' ', sql_content).strip()
        
        return sql_content
        
    except Exception:
        return xml_content
