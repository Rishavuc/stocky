from fastapi import APIRouter
from typing import List, Dict, Any
from app.schemas.schemas import QuizAnswerRequest, QuizAnswerResponse

router = APIRouter(prefix="/v1/learn", tags=["Learning & Courses"])

COURSES_CATALOG = [
    {
        "id": "course-1",
        "title": "Stock Market for Beginners Complete Playlist",
        "instructor": "CA Rachana Phadke Ranade",
        "platform": "YouTube",
        "topic": "basics",
        "language": "Hindi",
        "duration": "14 Hours",
        "lessons": 22,
        "rating": 4.9,
        "link": "https://www.youtube.com/@CARachanaRanade"
    },
    {
        "id": "course-2",
        "title": "Zerodha Varsity — Complete Modules 1-13",
        "instructor": "Karthik Rangappa (Zerodha)",
        "platform": "Zerodha Varsity",
        "topic": "basics",
        "language": "English",
        "duration": "40 Hours",
        "lessons": 96,
        "rating": 5.0,
        "link": "https://zerodha.com/varsity/"
    },
    {
        "id": "course-3",
        "title": "Technical Analysis & Candlestick Masterclass",
        "instructor": "Asset Yogi",
        "platform": "YouTube",
        "topic": "technical",
        "language": "Hindi",
        "duration": "8 Hours",
        "lessons": 14,
        "rating": 4.8,
        "link": "https://www.youtube.com/@AssetYogi"
    },
    {
        "id": "course-4",
        "title": "Options Trading: Understanding The Greeks & Strategies",
        "instructor": "PR Sundar / Sensibull Academy",
        "platform": "YouTube",
        "topic": "fno",
        "language": "English",
        "duration": "11 Hours",
        "lessons": 18,
        "rating": 4.7,
        "link": "https://www.sensibull.com"
    },
    {
        "id": "course-5",
        "title": "Valuation & Corporate Finance Masterclass",
        "instructor": "Prof. Aswath Damodaran (NYU Stern)",
        "platform": "Coursera",
        "topic": "fundamental",
        "language": "English",
        "duration": "32 Hours",
        "lessons": 26,
        "rating": 4.9,
        "link": "https://pages.stern.nyu.edu/~adamodar/"
    }
]

QUIZ_BANK = [
    {
        "id": 1,
        "question": "What does a P/E (Price-to-Earnings) Ratio of 25 indicate?",
        "options": [
            "Investors are paying ₹25 for every ₹1 of company earnings",
            "The stock will pay 25% dividend yield annually",
            "The stock price has grown 25 times in 5 years",
            "The company has 25% profit margin"
        ],
        "correct_option": 0,
        "explanation": "Correct! P/E ratio measures current share price relative to per-share earnings."
    },
    {
        "id": 2,
        "question": "In Options Trading, what does 'Theta' (θ) measure?",
        "options": [
            "Sensitivity of option price to underlying stock price",
            "Rate of time decay of the option premium over time",
            "Volatility sensitivity of the option contract",
            "Interest rate effect on future pricing"
        ],
        "correct_option": 1,
        "explanation": "Correct! Theta represents the rate at which an option’s value decays as expiration approaches."
    }
]

@router.get("/courses")
async def get_courses():
    return COURSES_CATALOG

@router.get("/quiz")
async def get_quiz():
    return [
        {"id": q["id"], "question": q["question"], "options": q["options"]}
        for q in QUIZ_BANK
    ]

@router.post("/quiz/answer", response_model=QuizAnswerResponse)
async def submit_quiz_answer(req: QuizAnswerRequest):
    q = next((item for item in QUIZ_BANK if item["id"] == req.question_id), None)
    if not q:
        return QuizAnswerResponse(correct=False, explanation="Question not found")

    is_correct = (req.selected_option == q["correct_option"])
    return QuizAnswerResponse(
        correct=is_correct,
        explanation=q["explanation"] if is_correct else "Incorrect option chosen.",
        next_question_id=req.question_id + 1 if req.question_id < len(QUIZ_BANK) else None
    )
