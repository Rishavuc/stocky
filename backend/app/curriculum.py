"""Segment-specific lessons, bookmarks and practice links."""

TOPICS = {
    "equities": [
        (
            "Ownership and diversification",
            "A share represents ownership in a company. Diversification spreads company-specific exposure; it does not remove market risk.",
            "Which action spreads company-specific risk?",
            [
                "Buy only one company",
                "Hold several companies across sectors",
                "Ignore the purchase price",
                "Use more leverage",
            ],
            1,
        ),
        (
            "Price versus business value",
            "Price is an observed transaction. Company value requires dated financial statements, cash flows and assumptions. A high price alone does not establish an expensive business.",
            "What is needed to discuss business value?",
            [
                "Only the share price",
                "An invented PE ratio",
                "Dated financial statements and assumptions",
                "A trending ticker",
            ],
            2,
        ),
    ],
    "intraday": [
        (
            "Bars and execution",
            "An intraday candle summarizes trades during a time interval. Its high and low do not reveal which occurred first. A submitted order must not fill on a past visible price.",
            "Can a daily candle reveal intraday ordering?",
            ["Always", "Only for profitable trades", "Only for index stocks", "No"],
            3,
        ),
        (
            "Slippage and risk",
            "The price you see can differ from your eventual fill. Fees, slippage and position size can turn a seemingly successful signal into a losing strategy.",
            "What can reduce hypothetical returns?",
            [
                "Fees and slippage",
                "More decimal places",
                "A smooth chart",
                "A dark theme",
            ],
            0,
        ),
    ],
    "derivatives": [
        (
            "Expiry and lot size",
            "Options reference an underlying and an expiry. Contracts have lot sizes; one option quantity is not necessarily one share. An option can expire worthless.",
            "Which property is essential for an option?",
            [
                "Logo color",
                "Expiry date",
                "Social popularity",
                "A fixed guaranteed return",
            ],
            1,
        ),
        (
            "Observed versus theoretical",
            "Open interest and quoted premiums are observations. Delta and theoretical value depend on a model and inputs. Keep derived estimates separate from exchange observations.",
            "Which figure is model-derived?",
            [
                "Observed last trade",
                "Published open interest",
                "Theoretical delta",
                "Exchange expiry",
            ],
            2,
        ),
    ],
    "funds": [
        (
            "NAV and fund units",
            "A mutual fund NAV is a periodically published unit value, not a streaming stock quote. Compare dates, plans and benchmark before comparing returns.",
            "Should NAV be presented as an intraday quote?",
            ["Yes", "Only during lunch", "Only for equity funds", "No"],
            3,
        ),
        (
            "SIP and return measurement",
            "An SIP invests cash on repeated dates. Total return must account for cash-flow timing; a simple percentage change is not the same as money-weighted return.",
            "What matters for SIP evaluation?",
            [
                "Cash-flow dates and amounts",
                "Only the final NAV",
                "Only the fund name",
                "Only a star rating",
            ],
            0,
        ),
    ],
    "crypto": [
        (
            "Quote currencies",
            "A crypto pair has a base and a quote currency. BTC/USD and BTC/USDT are distinct markets; neither is an INR price without a sourced conversion.",
            "What does the quote currency describe?",
            [
                "A guaranteed peg",
                "The currency used to price the base asset",
                "The market founder",
                "A fixed profit",
            ],
            1,
        ),
        (
            "Always-open markets",
            "Crypto trades continuously, but providers can be unavailable and liquidity changes. Missing observations must be identified rather than fabricated.",
            "What should happen when data is missing?",
            [
                "Generate random prices",
                "Call the old quote live",
                "Show a dated last observation or unavailable state",
                "Hide the source",
            ],
            2,
        ),
    ],
}


# Ported from the teammate `stocky` quiz bank (150634a). Appended after TOPICS so
# existing lesson ids, and the progress saved against them, stay unchanged.
# Three items were corrected: RSI wording, put-call ratio meaning, long-call payoff.
EXTRA_TOPICS = {
    "equities": [
        (
            "Price-to-earnings ratio",
            "P/E divides the share price by earnings per share. A P/E of 25 means buyers pay about 25 rupees per rupee of annual earnings. It needs dated, reported earnings and is most useful against similar companies.",
            "What does a P/E ratio of 25 indicate?",
            [
                "Investors pay about 25 rupees for every rupee of annual earnings",
                "The stock pays a 25% dividend yield",
                "The share price grew 25 times in five years",
                "The company has a 25% profit margin",
            ],
            0,
        ),
        (
            "Return on equity",
            "ROE is net income divided by shareholders' equity: profit generated per rupee owners have invested. Heavy borrowing can raise ROE without improving the business, so read it alongside debt.",
            "Which metric measures profitability on shareholders' equity?",
            ["Return on equity (ROE)", "Dividend yield", "Price-to-book ratio", "Current ratio"],
            0,
        ),
        (
            "Moving-average crossovers",
            "A golden cross is the 50-day simple average crossing above the 200-day average; a death cross is the reverse. Both lag price because they average the past, and neither guarantees what follows.",
            "When does a golden cross occur?",
            [
                "The 50-day average crosses below the 200-day average",
                "The 50-day average crosses above the 200-day average",
                "Price touches the upper Bollinger band",
                "RSI rises above 50",
            ],
            1,
        ),
        (
            "Reading RSI",
            "RSI compares recent gains with recent losses on a 0-100 scale. Readings above 70 are conventionally called overbought and below 30 oversold. Strong trends can stay overbought for a long time, so a high reading is not a sell signal by itself.",
            "What does an RSI of 82 on a daily chart describe?",
            [
                "A guaranteed fall in the next session",
                "Strong recent gains relative to losses, conventionally called overbought",
                "That the company is overvalued",
                "Unusually low trading volume",
            ],
            1,
        ),
    ],
    "intraday": [
        (
            "Intraday (MIS) versus delivery (CNC)",
            "MIS is an intraday product: brokers allow leverage within exchange margin rules, and open positions are squared off before the close. CNC is delivery: you pay in full and the shares settle into your demat account.",
            "What distinguishes MIS from CNC?",
            [
                "CNC positions are squared off the same day",
                "MIS uses leverage and must be closed the same day",
                "MIS shares settle into your demat account",
                "There is no difference",
            ],
            1,
        ),
    ],
    "derivatives": [
        (
            "Theta and time decay",
            "Theta measures how much an option's premium is expected to fall per day as expiry approaches, all else equal. Time decay works against option buyers and in favour of option sellers.",
            "What does theta measure?",
            [
                "Sensitivity to the underlying price",
                "Daily erosion of the premium as expiry approaches",
                "Sensitivity to implied volatility",
                "Sensitivity to interest rates",
            ],
            1,
        ),
        (
            "Put-call ratio",
            "PCR divides put volume or open interest by call volume or open interest. A rising PCR only says put activity is growing relative to calls. Puts are bought for hedging and written for income, so the reading is ambiguous on its own.",
            "What does a rising put-call ratio directly tell you?",
            [
                "The index will fall",
                "Put activity is growing relative to call activity",
                "Call writers are making losses",
                "Implied volatility is falling",
            ],
            1,
        ),
        (
            "Long call payoff",
            "Buying a call costs the premium. If the underlying stays below the strike at expiry, the most you lose is that premium. Above the strike, profit grows with the underlying and has no fixed ceiling.",
            "For a long call buyer, which is true?",
            [
                "Loss is unlimited and profit is capped",
                "Loss is limited to the premium; profit is theoretically unlimited",
                "Both loss and profit are unlimited",
                "Both loss and profit are limited to the premium",
            ],
            1,
        ),
    ],
}


def lessons():
    result = []
    for segment, topics in TOPICS.items():
        topics = topics + EXTRA_TOPICS.get(segment, [])
        for i, (title, body, question, options, correct) in enumerate(topics):
            result.append(
                {
                    "id": segment + "-" + str(i),
                    "segment": segment,
                    "level": "Beginner" if i == 0 else "Intermediate",
                    "title": title,
                    "body": body,
                    "question": question,
                    "options": options,
                    "correct": correct,
                    "minutes": 4,
                    "explanation": body,
                    "practice": "/replay"
                    if segment == "equities"
                    else "/markets?segment=" + segment,
                }
            )
    return result


GLOSSARY = [
    {
        "term": "OHLC",
        "definition": "Open, high, low and close observed within a candle.",
    },
    {
        "term": "NAV",
        "definition": "Net asset value per mutual-fund unit on a publication date.",
    },
    {
        "term": "FIFO",
        "definition": "First-in, first-out: match a sale against the earliest unmatched purchase.",
    },
    {
        "term": "Open interest",
        "definition": "The number of outstanding derivatives contracts.",
    },
    {
        "term": "Quantile",
        "definition": "A point in a distribution, used here to describe forecast ranges.",
    },
    {
        "term": "Slippage",
        "definition": "The difference between an assumed execution price and the eventual fill.",
    },
    {"term": "Drawdown", "definition": "The decline from an earlier portfolio peak."},
    {
        "term": "Baseline",
        "definition": "A simple alternative used to judge whether a more complex model adds value.",
    },
]


# External learning links, adapted from the `stocky` course catalog. Entries are
# labelled by what the link actually opens; unverified ratings, durations and
# lesson counts were dropped.
RESOURCES = [
    {"title": "Zerodha Varsity: free market modules", "provider": "Zerodha", "topic": "basics", "language": "English", "link": "https://zerodha.com/varsity/"},
    {"title": "Zerodha Varsity: futures trading module", "provider": "Zerodha", "topic": "derivatives", "language": "English", "link": "https://zerodha.com/varsity/module/futures-trading/"},
    {"title": "Financial Markets (Yale, Robert Shiller)", "provider": "Coursera", "topic": "basics", "language": "English", "link": "https://www.coursera.org/learn/financial-markets-global"},
    {"title": "Aswath Damodaran's valuation pages", "provider": "NYU Stern", "topic": "fundamentals", "language": "English", "link": "https://pages.stern.nyu.edu/~adamodar/"},
    {"title": "NSE learning resources", "provider": "NSE India", "topic": "basics", "language": "English", "link": "https://www.nseindia.com/learn"},
    {"title": "NPTEL course catalog (finance and economics)", "provider": "NPTEL", "topic": "fundamentals", "language": "English", "link": "https://nptel.ac.in/courses"},
    {"title": "CA Rachana Phadke Ranade channel", "provider": "YouTube", "topic": "basics", "language": "Hindi", "link": "https://www.youtube.com/@CARachanaRanade"},
    {"title": "Pranjal Kamra channel", "provider": "YouTube", "topic": "basics", "language": "Hindi", "link": "https://www.youtube.com/@PranjalKamra"},
    {"title": "Asset Yogi channel", "provider": "YouTube", "topic": "technical", "language": "Hindi", "link": "https://www.youtube.com/@AssetYogi"},
    {"title": "Rayner Teo channel", "provider": "YouTube", "topic": "technical", "language": "English", "link": "https://www.youtube.com/@RaynerTeo"},
    {"title": "TradingView education", "provider": "TradingView", "topic": "technical", "language": "English", "link": "https://www.tradingview.com/education/"},
    {"title": "Sensibull options education", "provider": "Sensibull", "topic": "derivatives", "language": "English", "link": "https://www.sensibull.com"},
    {"title": "Machine Learning for Trading", "provider": "Coursera", "topic": "algo", "language": "English", "link": "https://www.coursera.org/learn/machine-learning-for-trading"},
    {"title": "freeCodeCamp finance articles", "provider": "freeCodeCamp", "topic": "algo", "language": "English", "link": "https://www.freecodecamp.org/news/tag/finance/"},
    {"title": "MIT OpenCourseWare (search 'Blockchain and Money')", "provider": "MIT", "topic": "crypto", "language": "English", "link": "https://ocw.mit.edu"},
    {"title": "Whiteboard Crypto channel", "provider": "YouTube", "topic": "crypto", "language": "English", "link": "https://www.youtube.com/@WhiteboardCrypto"},
    {"title": "freeCodeCamp blockchain articles", "provider": "freeCodeCamp", "topic": "crypto", "language": "English", "link": "https://www.freecodecamp.org/news/tag/blockchain/"},
]
