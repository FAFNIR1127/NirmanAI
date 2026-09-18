import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional, Dict, Any

from backend.app.config import DATABASE_URL


class DocumentService:
    def _get_connection(self):
        return psycopg2.connect(DATABASE_URL)

    def get_corpus_summary(self) -> Dict[str, Any]:
        """Return summary statistics about document chunks in PostgreSQL."""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) as total_chunks, COUNT(DISTINCT source_file) as total_files, COUNT(DISTINCT project_code) as distinct_projects FROM document_chunks;")
                totals = cur.fetchone()

                cur.execute("SELECT document_type, COUNT(*) as count FROM document_chunks GROUP BY document_type ORDER BY count DESC;")
                by_type = cur.fetchall()

                cur.execute("SELECT reporting_month, COUNT(*) as count FROM document_chunks GROUP BY reporting_month ORDER BY reporting_month DESC LIMIT 12;")
                by_month = cur.fetchall()

                return {
                    "total_chunks": totals["total_chunks"],
                    "total_files": totals["total_files"],
                    "distinct_projects_referenced": totals["distinct_projects"],
                    "breakdown_by_document_type": [dict(r) for r in by_type],
                    "recent_reporting_months": [dict(r) for r in by_month]
                }
        finally:
            conn.close()

    def get_project_documents(self, project_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve historical document chunks associated with a specific project code."""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT chunk_id, content, source_file, relative_path, page_number,
                           reporting_month, reporting_year, document_type, project_code, metadata
                    FROM document_chunks
                    WHERE project_code = %s OR metadata->>'project_codes' LIKE %s
                    ORDER BY reporting_month DESC, page_number ASC
                    LIMIT %s;
                """, (project_code, f"%{project_code}%", limit))
                rows = cur.fetchall()
                
                results = []
                for r in rows:
                    res = dict(r)
                    res["citation"] = f"PAIMANA Report ({r['reporting_month']}), File: {r['source_file']}, Page {r['page_number']} - Project {project_code}"
                    results.append(res)
                return results
        finally:
            conn.close()
