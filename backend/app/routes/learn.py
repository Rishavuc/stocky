from fastapi import APIRouter
from typing import List, Dict, Any
from app.schemas.schemas import QuizAnswerRequest, QuizAnswerResponse

router = APIRouter(prefix="/v1/learn", tags=["Learning & Courses"])

COURSES_CATALOG = [
    {"id": "course-1", "title": "Stock Market for Beginners Complete Playlist", "instructor": "CA Rachana Phadke Ranade", "platform": "YouTube", "topic": "basics", "language": "Hindi", "duration": "14 Hours", "lessons": 22, "rating": 4.9, "link": "https://www.youtube.com/@CARachanaRanade"},
    {"id": "course-2", "title": "Zerodha Varsity — Complete Modules 1-13", "instructor": "Karthik Rangappa (Zerodha)", "platform": "Zerodha Varsity", "topic": "basics", "language": "English", "duration": "40 Hours", "lessons": 96, "rating": 5.0, "link": "https://zerodha.com/varsity/"},
    {"id": "course-3", "title": "Technical Analysis & Candlestick Masterclass", "instructor": "Asset Yogi", "platform": "YouTube", "topic": "technical", "language": "Hindi", "duration": "8 Hours", "lessons": 14, "rating": 4.8, "link": "https://www.youtube.com/@AssetYogi"},
    {"id": "course-4", "title": "Options Trading: Understanding The Greeks & Strategies", "instructor": "PR Sundar / Sensibull Academy", "platform": "YouTube", "topic": "fno", "language": "English", "duration": "11 Hours", "lessons": 18, "rating": 4.7, "link": "https://www.sensibull.com"},
    {"id": "course-5", "title": "Valuation & Corporate Finance Masterclass", "instructor": "Prof. Aswath Damodaran (NYU Stern)", "platform": "Coursera", "topic": "fundamental", "language": "English", "duration": "32 Hours", "lessons": 26, "rating": 4.9, "link": "https://pages.stern.nyu.edu/~adamodar/"},
    {"id": "course-6", "title": "Financial Markets Course", "instructor": "Prof. Robert Shiller (Yale University)", "platform": "Coursera", "topic": "basics", "language": "English", "duration": "33 Hours", "lessons": 28, "rating": 4.8, "link": "https://www.coursera.org/learn/financial-markets-global"},
    {"id": "course-7", "title": "Certification in Capital Markets & Derivatives", "instructor": "NSE India Academy", "platform": "NSE Academy", "topic": "fno", "language": "English", "duration": "20 Hours", "lessons": 16, "rating": 4.9, "link": "https://www.nseindia.com/learn"},
    {"id": "course-8", "title": "Algorithmic Trading & Quantitative Backtesting with Python", "instructor": "MIT OpenCourseWare / edX", "platform": "edX", "topic": "algo", "language": "English", "duration": "24 Hours", "lessons": 20, "rating": 4.8, "link": "https://www.edx.org"},
    {"id": "course-9", "title": "Crypto, Bitcoin & Blockchain Technology Decoded", "instructor": "Gary Gensler (MIT Sloan)", "platform": "YouTube", "topic": "crypto", "language": "English", "duration": "26 Hours", "lessons": 24, "rating": 4.9, "link": "https://ocw.mit.edu"},
    {"id": "course-10", "title": "Personal Finance, Mutual Funds & SIP Blueprint", "instructor": "CA Rachana Phadke Ranade", "platform": "YouTube", "topic": "basics", "language": "Hindi", "duration": "9 Hours", "lessons": 16, "rating": 4.8, "link": "https://www.youtube.com/@CARachanaRanade"},
    {"id": "course-11", "title": "Stock Market Investing for Beginners", "instructor": "Pranjal Kamra", "platform": "YouTube", "topic": "basics", "language": "Hindi", "duration": "7 Hours", "lessons": 12, "rating": 4.8, "link": "https://www.youtube.com/@PranjalKamra"},
    {"id": "course-12", "title": "Price Action & Swing Trading Blueprint", "instructor": "Rayner Teo", "platform": "YouTube", "topic": "technical", "language": "English", "duration": "10 Hours", "lessons": 18, "rating": 4.7, "link": "https://www.youtube.com/@RaynerTeo"},
    {"id": "course-13", "title": "Volume Price Analysis & Wyckoff Method", "instructor": "Anna Coulling / Trade with Trend", "platform": "YouTube", "topic": "technical", "language": "English", "duration": "6 Hours", "lessons": 11, "rating": 4.6, "link": "https://www.youtube.com/results?search_query=wyckoff+volume+price+analysis"},
    {"id": "course-14", "title": "TradingView Charting & Indicator Mastery", "instructor": "TradingView Education", "platform": "TradingView", "topic": "technical", "language": "English", "duration": "5 Hours", "lessons": 10, "rating": 4.7, "link": "https://www.tradingview.com/education/"},
    {"id": "course-15", "title": "Futures & Options Complete Bootcamp", "instructor": "Karthik Rangappa (Zerodha)", "platform": "Zerodha Varsity", "topic": "fno", "language": "English", "duration": "16 Hours", "lessons": 24, "rating": 4.9, "link": "https://zerodha.com/varsity/module/futures-trading/"},
    {"id": "course-16", "title": "Option Greeks & Payoff Strategy Lab", "instructor": "Sensibull Academy", "platform": "YouTube", "topic": "fno", "language": "English", "duration": "8 Hours", "lessons": 14, "rating": 4.7, "link": "https://www.sensibull.com"},
    {"id": "course-17", "title": "Nifty & Bank Nifty Option Selling Systems", "instructor": "Bhanu Pratap", "platform": "YouTube", "topic": "fno", "language": "Hindi", "duration": "12 Hours", "lessons": 20, "rating": 4.6, "link": "https://www.youtube.com/@BhanuPratap"},
    {"id": "course-18", "title": "Financial Statement Analysis & Ratio Deep Dive", "instructor": "NSE Academy", "platform": "NSE Academy", "topic": "fundamental", "language": "English", "duration": "18 Hours", "lessons": 22, "rating": 4.8, "link": "https://www.nseindia.com/learn"},
    {"id": "course-19", "title": "Value Investing & Margin of Safety", "instructor": "NPTEL / IIT Faculty", "platform": "NSE Academy", "topic": "fundamental", "language": "English", "duration": "14 Hours", "lessons": 18, "rating": 4.7, "link": "https://nptel.ac.in/courses"},
    {"id": "course-20", "title": "Python for Finance & Algo Backtesting", "instructor": "freeCodeCamp", "platform": "freeCodeCamp", "topic": "algo", "language": "English", "duration": "12 Hours", "lessons": 15, "rating": 4.8, "link": "https://www.freecodecamp.org/news/tag/finance/"},
    {"id": "course-21", "title": "Machine Learning & Deep Learning for Trading", "instructor": "DeepLearning.AI (Coursera)", "platform": "Coursera", "topic": "algo", "language": "English", "duration": "20 Hours", "lessons": 22, "rating": 4.7, "link": "https://www.coursera.org/learn/machine-learning-for-trading"},
    {"id": "course-22", "title": "Crypto Trading & DeFi Yield Strategies", "instructor": "Whiteboard Crypto", "platform": "YouTube", "topic": "crypto", "language": "English", "duration": "9 Hours", "lessons": 16, "rating": 4.7, "link": "https://www.youtube.com/@WhiteboardCrypto"},
    {"id": "course-23", "title": "Ethereum Smart Contracts with Solidity", "instructor": "freeCodeCamp", "platform": "freeCodeCamp", "topic": "crypto", "language": "English", "duration": "16 Hours", "lessons": 20, "rating": 4.8, "link": "https://www.freecodecamp.org/news/tag/blockchain/"},
    {"id": "course-24", "title": "Risk Management & Trading Psychology", "instructor": "Mark Douglas (adapted lectures)", "platform": "YouTube", "topic": "basics", "language": "English", "duration": "5 Hours", "lessons": 9, "rating": 4.9, "link": "https://www.youtube.com/results?search_query=mark+douglas+trading+psychology"},
    {"id": "course-25", "title": "Portfolio Management & Asset Allocation", "instructor": "NPTEL / IIT Faculty", "platform": "Coursera", "topic": "basics", "language": "English", "duration": "13 Hours", "lessons": 17, "rating": 4.7, "link": "https://nptel.ac.in/courses"},
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
    return QuizAnswerResponse(
        correct=is_correct,
        explanation=q["explanation"] if is_correct else "Incorrect option chosen.",
        next_question_id=req.question_id + 1 if req.question_id < len(QUIZ_BANK) else None
    )
