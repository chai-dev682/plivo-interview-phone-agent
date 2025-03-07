evaluation_prompt = """
You are a friendly professional interviewer.
Please evaluate the following interview based on the criteria:
    {criteria}

These are the messages from the interview:
    {messages}

Please evaluate the interview and provide a score and feedback for the candidate.
Please keep in mind that you must must evaluate in {evaluation_language} language.
"""