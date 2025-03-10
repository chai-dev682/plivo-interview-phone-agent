import pymysql
from app.core.config import settings
import json

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

    def _get_connection(self):
        return pymysql.connect(**self.config)
    
    def initialize(self):
        """Create the Interview table if it doesn't exist"""
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Interview (
                        interview_id INT AUTO_INCREMENT PRIMARY KEY,
                        job_id VARCHAR(255),
                        phone_number VARCHAR(20),
                        questions JSON,
                        evaluation_criteria JSON,
                        interview_language VARCHAR(50),
                        evaluation_language VARCHAR(50),
                        call_recording_url VARCHAR(255) NULL,
                        is_completed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            connection.commit()
        finally:
            connection.close()
    
    async def get_interview(self, interview_id: int):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM Interview WHERE interview_id = %s", (interview_id,))
                result = cursor.fetchone()
                if result:
                    # Parse JSON strings back into Python lists
                    result['questions'] = json.loads(result['questions'])
                    result['evaluation_criteria'] = json.loads(result['evaluation_criteria'])
                return result
        finally:
            connection.close()
    
    async def insert_interview(self, interview):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                # Check for existing interview with same phone number and job ID
                check_sql = """
                    SELECT interview_id FROM Interview 
                    WHERE phone_number = %s AND job_id = %s
                """
                cursor.execute(check_sql, (interview.phone_number, interview.job_id))
                if cursor.fetchone():
                    raise ValueError(f"Interview already exists for phone number {interview.phone_number} and job ID {interview.job_id}")

                sql = """
                    INSERT INTO Interview (
                        job_id, phone_number, questions,
                        evaluation_criteria, interview_language, evaluation_language,
                        call_recording_url, is_completed, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                questions_json = json.dumps(interview.questions)
                criteria_json = json.dumps(interview.evaluation_criteria)
                
                cursor.execute(sql, (
                    interview.job_id,
                    interview.phone_number,
                    questions_json,
                    criteria_json,
                    interview.interview_language,
                    interview.evaluation_language,
                    interview.call_recording_url,
                    interview.is_completed,
                    interview.created_at
                ))
                connection.commit()

                new_id = cursor.lastrowid

                return new_id
        finally:
            connection.close()
    
    async def get_interview_by_phone(self, phone_number: str):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM Interview WHERE phone_number = %s AND is_completed = 0 limit 1", (phone_number,))
                result = cursor.fetchone()
                if result:
                    result['questions'] = json.loads(result['questions'])
                    result['evaluation_criteria'] = json.loads(result['evaluation_criteria'])
                    return result
                else:
                    return None
        finally:
            connection.close()

    async def update_interview(self, interview_id: int, update_data: dict):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                # Convert questions and evaluation_criteria to JSON strings if present
                if 'questions' in update_data:
                    update_data['questions'] = json.dumps(update_data['questions'])
                if 'evaluation_criteria' in update_data:
                    update_data['evaluation_criteria'] = json.dumps(update_data['evaluation_criteria'])

                # Build the UPDATE query dynamically based on provided fields
                set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
                values = list(update_data.values())
                
                sql = f"UPDATE Interview SET {set_clause} WHERE interview_id = %s"
                values.append(interview_id)  # Add interview_id to values list
                cursor.execute(sql, values)
                connection.commit()
                
                if cursor.rowcount > 0:
                    # Get the updated record
                    cursor.execute("SELECT * FROM Interview WHERE interview_id = %s", (interview_id,))
                    result = cursor.fetchone()
                    if result:
                        # Parse JSON strings back into Python objects
                        result['questions'] = json.loads(result['questions'])
                        result['evaluation_criteria'] = json.loads(result['evaluation_criteria'])
                    return result
        finally:
            connection.close()

    async def delete_interview(self, interview_id: int) -> bool:
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM Interview WHERE interview_id = %s", (interview_id,))
                success = cursor.rowcount > 0
            connection.commit()
            return success
        finally:
            connection.close()

    async def get_interviews_by_phone(self, phone_number: str):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM Interview WHERE phone_number = %s", (phone_number,))
                results = cursor.fetchall()
                for result in results:
                    result['questions'] = json.loads(result['questions'])
                    result['evaluation_criteria'] = json.loads(result['evaluation_criteria'])
                return results
        finally:
            connection.close()
    
    async def update_interview_by_job_id(self, job_id: str, interview_id: int, update_data: dict):
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                # Convert questions and evaluation_criteria to JSON strings if present
                if 'questions' in update_data:
                    update_data['questions'] = json.dumps(update_data['questions'])
                if 'evaluation_criteria' in update_data:
                    update_data['evaluation_criteria'] = json.dumps(update_data['evaluation_criteria'])

                # Build the UPDATE query dynamically based on provided fields
                set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
                values = list(update_data.values())
                
                sql = f"UPDATE Interview SET {set_clause} WHERE interview_id = %s AND job_id = %s"
                values.append(interview_id)  # Add interview_id to values list
                values.append(job_id)  # Add job_id to values list
                cursor.execute(sql, values)
                connection.commit()
                
                if cursor.rowcount > 0:
                    # Get the updated record
                    cursor.execute("SELECT * FROM Interview WHERE interview_id = %s AND job_id = %s", (interview_id, job_id))
                    result = cursor.fetchone()
                    if result:
                        # Parse JSON strings back into Python objects
                        result['questions'] = json.loads(result['questions'])
                        result['evaluation_criteria'] = json.loads(result['evaluation_criteria'])
                    return result
                connection.commit()
        finally:
            connection.close()

mysql_service = MySQLService()