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


def lessons():
    result = []
    for segment, topics in TOPICS.items():
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
