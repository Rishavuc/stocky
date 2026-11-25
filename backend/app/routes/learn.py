from fastapi import APIRouter
from typing import List, Dict, Any
from app.schemas.schemas import QuizAnswerRequest, QuizAnswerResponse

router = APIRouter(prefix="/v1/learn", tags=["Learning & Courses"])

COURSES_CATALOG = [
    {"id": "course-1", "title": "Stock Market for Beginners Complete Playlist", "instructor": "CA Rachana Phadke Ranade", "platform": "YouTube", "topic": "basics", "language": "Hindi", "duration": "14 Hours", "lessons": 22, "rating": 4.9, "link": "https://www.youtube.com/@CARachanaRanade", "video_url": "https://www.youtube.com/watch?v=Xn7KWR9EOGQ", "video_title": "Basics of Stock Market For Beginners - Lecture 1", "video_author": "CA Rachana Phadke Ranade"},
    {"id": "course-2", "title": "Zerodha Varsity — Complete Modules 1-13", "instructor": "Karthik Rangappa (Zerodha)", "platform": "Zerodha Varsity", "topic": "basics", "language": "English", "duration": "40 Hours (Self-paced)", "lessons": 96, "rating": 5.0, "link": "https://zerodha.com/varsity/", "video_url": "https://www.youtube.com/watch?v=GcZW24SkbHM", "video_title": "1. Why should you invest? | Zerodha Varsity", "video_author": "Zerodha Varsity"},
    {"id": "course-3", "title": "Technical Analysis & Candlestick Masterclass", "instructor": "Asset Yogi", "platform": "YouTube", "topic": "technical", "language": "Hindi", "duration": "8 Hours", "lessons": 14, "rating": 4.8, "link": "https://www.youtube.com/@AssetYogi", "video_url": "https://www.youtube.com/watch?v=miaGZZusRnE", "video_title": "Candlestick Trading Full Course", "video_author": "Trade with Purab"},
    {"id": "course-4", "title": "Options Trading: Understanding The Greeks & Strategies", "instructor": "PR Sundar / Sensibull Academy", "platform": "YouTube", "topic": "fno", "language": "English", "duration": "11 Hours", "lessons": 18, "rating": 4.7, "link": "https://www.sensibull.com", "video_url": "https://www.youtube.com/watch?v=Ca66fN3oP1U", "video_title": "Option Greeks Explained - Theta Delta Gamma Vega RHO", "video_author": "Pushkar Raj Thakur"},
    {"id": "course-5", "title": "Valuation & Corporate Finance Masterclass", "instructor": "Prof. Aswath Damodaran (NYU Stern)", "platform": "Coursera", "topic": "fundamental", "language": "English", "duration": "32 Hours", "lessons": 26, "rating": 4.9, "link": "https://pages.stern.nyu.edu/~adamodar/", "video_url": "https://www.youtube.com/watch?v=znmQ7oMiQrM", "video_title": "Session 1: Introduction to Valuation", "video_author": "Aswath Damodaran"},
    {"id": "course-6", "title": "Financial Markets Course", "instructor": "Prof. Robert Shiller (Yale University)", "platform": "Coursera", "topic": "basics", "language": "English", "duration": "33 Hours", "lessons": 28, "rating": 4.8, "link": "https://www.coursera.org/learn/financial-markets-global", "video_url": "https://www.youtube.com/watch?v=WQui_3Hpmmc", "video_title": "1. Introduction and What this Course Will Do for You", "video_author": "YaleCourses"},
    {"id": "course-7", "title": "Certification in Capital Markets & Derivatives", "instructor": "NSE India Academy", "platform": "NSE Academy", "topic": "fno", "language": "English", "duration": "20 Hours", "lessons": 16, "rating": 4.9, "link": "https://www.youtube.com/watch?v=YJx2JjdIgRQ", "video_url": "https://www.youtube.com/watch?v=YJx2JjdIgRQ", "video_title": "Capital Market Dealers Module - NSE NCFM Certification Tutorial", "video_author": "NIFM Institute"},
    {"id": "course-8", "title": "Algorithmic Trading & Quantitative Backtesting with Python", "instructor": "MIT OpenCourseWare / edX", "platform": "edX", "topic": "algo", "language": "English", "duration": "24 Hours", "lessons": 20, "rating": 4.8, "link": "https://www.edx.org", "video_url": "https://www.youtube.com/watch?v=uk0irecL95o", "video_title": "Start Algo Trading in Python (Part 1)", "video_author": "Algorithm Trading"},
    {"id": "course-9", "title": "Crypto, Bitcoin & Blockchain Technology Decoded", "instructor": "Gary Gensler (MIT Sloan)", "platform": "YouTube", "topic": "crypto", "language": "English", "duration": "26 Hours", "lessons": 24, "rating": 4.9, "link": "https://ocw.mit.edu", "video_url": "https://www.youtube.com/watch?v=EH6vE97qIP4", "video_title": "1. Introduction for 15.S12 Blockchain and Money, Fall 2018", "video_author": "MIT OpenCourseWare"},
    {"id": "course-10", "title": "Personal Finance, Mutual Funds & SIP Blueprint", "instructor": "CA Rachana Phadke Ranade", "platform": "YouTube", "topic": "basics", "language": "Hindi", "duration": "9 Hours", "lessons": 16, "rating": 4.8, "link": "https://www.youtube.com/@CARachanaRanade", "video_url": "https://www.youtube.com/watch?v=6sq2o1atWLY", "video_title": "Beginners guide to personal finance", "video_author": "Zerodha Varsity"},
    {"id": "course-11", "title": "Stock Market Investing for Beginners", "instructor": "Pranjal Kamra", "platform": "YouTube", "topic": "basics", "language": "Hindi", "duration": "7 Hours", "lessons": 12, "rating": 4.8, "link": "https://www.youtube.com/@PranjalKamra", "video_url": "https://www.youtube.com/watch?v=3UF0ymVdYLA", "video_title": "Stock Market For Beginners - How can Beginners Start Investing?", "video_author": "Pranjal Kamra"},
    {"id": "course-12", "title": "Price Action & Swing Trading Blueprint", "instructor": "Rayner Teo", "platform": "YouTube", "topic": "technical", "language": "English", "duration": "10 Hours", "lessons": 18, "rating": 4.7, "link": "https://www.youtube.com/@RaynerTeo", "video_url": "https://www.youtube.com/watch?v=PuboYnBc0t8", "video_title": "Support and Resistance Secrets: Powerful Strategies", "video_author": "Rayner Teo"},
    {"id": "course-13", "title": "Volume Price Analysis & Wyckoff Method", "instructor": "Anna Coulling / Trade with Trend", "platform": "YouTube", "topic": "technical", "language": "English", "duration": "6 Hours", "lessons": 11, "rating": 4.6, "link": "https://www.youtube.com/watch?v=M-WjjX6X3Pw", "video_url": "https://www.youtube.com/watch?v=M-WjjX6X3Pw", "video_title": "The Secret Language of Volume: Richard Wyckoff's Lessons", "video_author": "Richard Wyckoff Methods"},
    {"id": "course-14", "title": "TradingView Charting & Indicator Mastery", "instructor": "TradingView Education", "platform": "TradingView", "topic": "technical", "language": "English", "duration": "5 Hours", "lessons": 10, "rating": 4.7, "link": "https://www.tradingview.com/education/", "video_url": "https://www.youtube.com/watch?v=sMHkuex7r8M", "video_title": "Tradingview Tutorial FULL Course", "video_author": "Neeraj Joshi"},
    {"id": "course-15", "title": "Futures & Options Complete Bootcamp", "instructor": "Karthik Rangappa (Zerodha)", "platform": "Zerodha Varsity", "topic": "fno", "language": "English", "duration": "16 Hours", "lessons": 24, "rating": 4.9, "link": "https://zerodha.com/varsity/module/futures-trading/", "video_url": "https://www.youtube.com/watch?v=J0sKv8cples", "video_title": "1. Introduction to forwards market | Zerodha Varsity", "video_author": "Zerodha Varsity"},
    {"id": "course-16", "title": "Option Greeks & Payoff Strategy Lab", "instructor": "Sensibull Academy", "platform": "YouTube", "topic": "fno", "language": "English", "duration": "8 Hours", "lessons": 14, "rating": 4.7, "link": "https://www.sensibull.com", "video_url": "https://www.youtube.com/watch?v=5q6wxifVgkQ", "video_title": "Sensibull Tutorial - Build Your Option Trading Strategy", "video_author": "Neeraj Joshi"},
    {"id": "course-17", "title": "Nifty & Bank Nifty Option Selling Systems", "instructor": "Bhanu Pratap", "platform": "YouTube", "topic": "fno", "language": "Hindi", "duration": "12 Hours", "lessons": 20, "rating": 4.6, "link": "https://www.youtube.com/watch?v=XEw3xd1fQZk", "video_url": "https://www.youtube.com/watch?v=XEw3xd1fQZk", "video_title": "NIFTY Option Selling Strategy - 800 Point Hedging Setup", "video_author": "Vishal Bhingaradiya"},
    {"id": "course-18", "title": "Financial Statement Analysis & Ratio Deep Dive", "instructor": "NSE Academy", "platform": "NSE Academy", "topic": "fundamental", "language": "English", "duration": "18 Hours", "lessons": 22, "rating": 4.8, "link": "https://www.youtube.com/watch?v=3W_LwpeG8c8", "video_url": "https://www.youtube.com/watch?v=3W_LwpeG8c8", "video_title": "FINANCIAL RATIOS: How to Analyze Financial Statements", "video_author": "Accounting Stuff"},
    {"id": "course-19", "title": "Value Investing & Margin of Safety", "instructor": "NPTEL / IIT Faculty", "platform": "NSE Academy", "topic": "fundamental", "language": "English", "duration": "14 Hours", "lessons": 18, "rating": 4.7, "link": "https://nptel.ac.in/courses", "video_url": "https://www.youtube.com/watch?v=D8TYIYHwiY0", "video_title": "Margin of Safety Summary (Seth Klarman)", "video_author": "The Swedish Investor"},
    {"id": "course-20", "title": "Python for Finance & Algo Backtesting", "instructor": "freeCodeCamp", "platform": "freeCodeCamp", "topic": "algo", "language": "English", "duration": "12 Hours", "lessons": 15, "rating": 4.8, "link": "https://www.freecodecamp.org/news/tag/finance/", "video_url": "https://www.youtube.com/watch?v=GaZm_rcCsGI", "video_title": "How To Use Python For Backtesting Strategies", "video_author": "FessorPro"},
    {"id": "course-21", "title": "Machine Learning & Deep Learning for Trading", "instructor": "DeepLearning.AI (Coursera)", "platform": "Coursera", "topic": "algo", "language": "English", "duration": "20 Hours", "lessons": 22, "rating": 4.7, "link": "https://www.youtube.com/watch?v=CbTU92pbDKw", "video_url": "https://www.youtube.com/watch?v=CbTU92pbDKw", "video_title": "Stock Price Prediction & Forecasting with LSTM Neural Networks in Python", "video_author": "Greg Hogg"},
    {"id": "course-22", "title": "Crypto Trading & DeFi Yield Strategies", "instructor": "Whiteboard Crypto", "platform": "YouTube", "topic": "crypto", "language": "English", "duration": "9 Hours", "lessons": 16, "rating": 4.7, "link": "https://www.youtube.com/@WhiteboardCrypto", "video_url": "https://www.youtube.com/watch?v=17QRFlml4pA", "video_title": "What is DeFi? (Decentralized Finance Animated)", "video_author": "Whiteboard Crypto"},
    {"id": "course-23", "title": "Ethereum Smart Contracts with Solidity", "instructor": "freeCodeCamp", "platform": "freeCodeCamp", "topic": "crypto", "language": "English", "duration": "16 Hours", "lessons": 20, "rating": 4.8, "link": "https://www.freecodecamp.org/news/tag/blockchain/", "video_url": "https://www.youtube.com/watch?v=X1Kx9NWVRwI", "video_title": "Solidity Tutorial: Create Your First Smart Contract on Ethereum", "video_author": "Justin Salmon"},
    {"id": "course-24", "title": "Risk Management & Trading Psychology", "instructor": "Mark Douglas (adapted lectures)", "platform": "YouTube", "topic": "basics", "language": "English", "duration": "5 Hours", "lessons": 9, "rating": 4.9, "link": "https://www.youtube.com/watch?v=sg4YzRhILFE", "video_url": "https://www.youtube.com/watch?v=sg4YzRhILFE", "video_title": "Mark Douglas Discussed Trading Psychology, Risk and more", "video_author": "R.E.M"},
    {"id": "course-25", "title": "Portfolio Management & Asset Allocation", "instructor": "NPTEL / IIT Faculty", "platform": "Coursera", "topic": "basics", "language": "English", "duration": "13 Hours", "lessons": 17, "rating": 4.7, "link": "https://nptel.ac.in/courses", "video_url": "https://www.youtube.com/watch?v=ope5Y3Mrsaw", "video_title": "Mod-01 Lec-01 Introduction to Investment Management", "video_author": "nptelhrd"},
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
    },
    {
        "id": 3,
        "question": "What is the primary difference between Intraday (MIS) and Delivery (CNC)?",
        "options": [
            "MIS offers leverage and must be squared off the same day",
            "CNC orders cannot be sold for 1 full year",
            "MIS orders do not incur any transaction tax",
            "CNC is exclusively for crypto trading"
        ],
        "correct_option": 0,
        "explanation": "Correct! MIS (Margin Intraday Square-off) is leveraged and auto-squared before market close."
    },
    {
        "id": 4,
        "question": "An RSI reading of 82 on a daily chart most likely signals…",
        "options": [
            "The stock is oversold and due for a bounce",
            "The stock is overbought and may be due for a pullback",
            "The trend has permanently reversed to bearish",
            "Volume is about to spike by exactly 82%"
        ],
        "correct_option": 1,
        "explanation": "Correct! RSI above 70 is conventionally 'overbought' (below 30 is 'oversold')."
    },
    {
        "id": 5,
        "question": "What does a rising Put-Call Ratio (PCR) in an index suggest?",
        "options": [
            "Traders are piling into calls, expecting a rally",
            "Relatively more puts are being written than calls",
            "The market is closed for settlement",
            "Futures premiums have turned negative"
        ],
        "correct_option": 1,
        "explanation": "Correct! A rising PCR means put activity is growing relative to call activity."
    },
    {
        "id": 6,
        "question": "Which metric best measures a company's profitability on shareholder equity?",
        "options": [
            "Return on Equity (ROE)",
            "Debt-to-Equity ratio",
            "Current ratio",
            "Price-to-Book ratio"
        ],
        "correct_option": 0,
        "explanation": "Correct! ROE = Net Income / Shareholders' Equity."
    },
    {
        "id": 7,
        "question": "A 'Golden Cross' occurs when…",
        "options": [
            "The 50-day SMA crosses above the 200-day SMA",
            "The 200-day SMA crosses above the 50-day SMA",
            "Price touches the upper Bollinger Band",
            "The VIX drops below 10"
        ],
        "correct_option": 0,
        "explanation": "Correct! A Golden Cross is the 50-day SMA moving above the 200-day SMA (bullish)."
    },
    {
        "id": 8,
        "question": "For a long Call option buyer, which risk is unlimited?",
        "options": [
            "Maximum loss is unlimited",
            "Maximum profit is unlimited",
            "Both profit and loss are unlimited",
            "Neither profit nor loss is unlimited"
        ],
        "correct_option": 1,
        "explanation": "Correct! A long call has limited loss (premium paid) but theoretically unlimited upside."
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
    correct_option = int(q["correct_option"])
    correct_answer = q["options"][correct_option]
    explanation = (
        q["explanation"]
        if is_correct
        else f"Not quite — the correct answer is: {correct_answer}."
    )

    ids = [item["id"] for item in QUIZ_BANK]
    pos = ids.index(req.question_id) if req.question_id in ids else -1
    next_question_id = ids[pos + 1] if pos >= 0 and pos + 1 < len(ids) else None

    return QuizAnswerResponse(
        correct=is_correct,
        explanation=explanation,
        next_question_id=next_question_id,
        correct_option=correct_option,
        correct_answer=correct_answer,
    )
