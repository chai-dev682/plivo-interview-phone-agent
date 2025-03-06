import pymysql
from app.core.config import settings
from app.schemas.interview import Interview

class MySQLService:
    def __init__(self):
        self.config = {
            "host": settings.DB_HOST,
            "user": settings.DB_USER,
            "password": settings.DB_PASSWORD,
            "db": settings.DB_NAME,
            "port": settings.DB_PORT,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": 10,
            "read_timeout": 10,
            "write_timeout": 10
        }
        self.initialize()

    def _get_connection(self):
        return pymysql.connect(**self.config)
    
    def initialize(self):
        """Create the Interview table if it doesn't exist"""
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS Interview (
                    id INT PRIMARY KEY,
                    job_id TEXT,
                    phone_number TEXT,
                    questions JSON,
                    evaluation_criteria JSON,
                    interview_language TEXT,
                    evaluation_language TEXT,
                    is_completed BOOLEAN
                )
                """)
            connection.commit()
        finally:
            connection.close()
    
    async def get_interview(self, interview_id: str):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM Interview WHERE interview_id = %s", (interview_id,))
                return cursor.fetchone()
        finally:
            connection.close()
    
    def insert_interview(self, interview: Interview):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """INSERT INTO Interview 
                        (id, job_id, phone_number, questions, evaluation_criteria, interview_language, evaluation_language, is_completed)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (
                    interview.interview_id,
                    interview.job_id,
                    interview.phone_number,
                    interview.questions,
                    interview.evaluation_criteria,
                    interview.interview_language,
                    interview.evaluation_language,
                    interview.is_completed,
                    interview.created_at
                ))
            connection.commit()
        finally:
            connection.close()

mysql_service = MySQLService()