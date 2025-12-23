import csv
import logging
from pathlib import Path
from .db import Database

logger = logging.getLogger(__name__)

class DataExporter:
    def __init__(self, db: Database, export_dir: str = "exports"):
        self.db = db
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_run(self, run_id: str):
        """
        Exports articles and comments for a specific run to CSV.
        """
        logger.info(f"Starting export for run_id: {run_id}")
        
        self._export_table(
            table="articles",
            filename=f"articles_{run_id}.csv",
            where_clause="WHERE run_id = ?",
            params=(run_id,)
        )
        
        self._export_table(
            table="comments",
            filename=f"comments_{run_id}.csv",
            where_clause="WHERE run_id = ?",
            params=(run_id,)
        )
        
        # Export run log (append mode usually, but here we dump current run info)
        self._export_table(
            table="runs",
            filename=f"run_log_{run_id}.csv",
            where_clause="WHERE run_id = ?",
            params=(run_id,)
        )

    def _export_table(self, table: str, filename: str, where_clause: str = "", params: tuple = ()):
        filepath = self.export_dir / filename
        conn = self.db.get_connection()
        try:
            # Get headers
            cursor = conn.execute(f"SELECT * FROM {table} LIMIT 0")
            headers = [description[0] for description in cursor.description]
            
            # Get data
            sql = f"SELECT * FROM {table} {where_clause}"
            cursor = conn.execute(sql, params)
            
            row_count = 0
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                
                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    writer.writerows(rows)
                    row_count += len(rows)
            
            logger.info(f"Exported {row_count} rows from '{table}' to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export table {table}: {e}")
        finally:
            conn.close()