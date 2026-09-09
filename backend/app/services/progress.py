from app.database.connection import get_connection


def save_quiz_result(
    user_id: int,
    score: int,
    total_questions: int
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO quiz_results (
                    user_id,
                    score,
                    total_questions
                )
                VALUES (%s, %s, %s)
                RETURNING id, score, total_questions, created_at
                """,
                (
                    user_id,
                    score,
                    total_questions
                )
            )

            result = cursor.fetchone()

        conn.commit()

    return {
        "id": result[0],
        "score": result[1],
        "total_questions": result[2],
        "created_at": result[3]
    }


def get_quiz_results(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    score,
                    total_questions,
                    created_at
                FROM quiz_results
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )

            results = cursor.fetchall()

    return [
        {
            "id": result[0],
            "score": result[1],
            "total_questions": result[2],
            "created_at": result[3]
        }
        for result in results
    ]