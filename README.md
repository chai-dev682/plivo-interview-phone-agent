# Interview Phone Server using Plivo

## Overview

The Interview Phone Server project is designed to manage and conduct automated phone interviews with candidates. This solution offers seamless handling and processing of interviews, using conversational AI technologies to interact with candidates, and evaluates their responses based on predefined criteria. It is specifically tailored to work with Plivo phone numbers and supports scheduling, conducting, and evaluating interviews through a series of RESTful API endpoints.

## Core Features

- Scheduling Interviews: Store interview details such as phone number, interview questions, evaluation criteria, and languages via the /schedule_interview endpoint.
- Handling Calls: Use the /answer_call endpoint to handle incoming calls, ask candidates the associated questions, and process their responses in a specified language.
- Multilingual Support: Conduct interviews and evaluate responses in specified interview and evaluation languages using advanced speech-to-text and text-to-speech technologies.
- Evaluation and Webhook Notifications: Evaluates candidate responses and sends a detailed evaluation score through a webhook to an external URL.
