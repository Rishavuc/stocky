# Measured experiment results

Generated from the saved reports. Model selection uses validation error. The final test is not used to choose a winner.

| Instrument | Currency | Horizon | Selected model | Test MAE | Baseline MAE | Lower error than baseline |
| --- | --- | --- | --- | ---: | ---: | --- |
| BANKNIFTY | INR | 1 observations | LSTM | 504.8693 | 501.5578 | No |
| BANKNIFTY | INR | 5 observations | LSTM | 1166.5480 | 1152.9463 | No |
| BHARTIARTL | INR | 1 observations | Last-price baseline | 21.2425 | 21.2425 | No |
| BHARTIARTL | INR | 5 observations | Last-price baseline | 45.5166 | 45.5166 | No |
| BTCUSDT | USDT | 1 observations | Last-price baseline | 977.8735 | 977.8735 | No |
| BTCUSDT_1h | USDT | 1 observations | Last-price baseline | 223.3412 | 223.3412 | No |
| BTCUSDT_1h | USDT | 24 observations | Gradient boosting | 1240.8697 | 1161.1478 | No |
| BTCUSDT | USDT | 24 observations | LSTM | 5785.7370 | 5430.2211 | No |
| BTCUSD | USD | 1 observations | LSTM | 1121.3946 | 1065.9514 | No |
| BTCUSD | USD | 24 observations | Last-price baseline | 6040.5745 | 6040.5745 | No |
| ETHUSDT | USDT | 1 observations | Last-price baseline | 38.3194 | 38.3194 | No |
| ETHUSDT_1h | USDT | 1 observations | Last-price baseline | 7.6853 | 7.6853 | No |
| ETHUSDT_1h | USDT | 24 observations | Last-price baseline | 49.8744 | 49.8744 | No |
| ETHUSDT | USDT | 24 observations | Moving-average baseline | 260.4949 | 247.6273 | No |
| ETHUSD | USD | 1 observations | Last-price baseline | 40.8398 | 40.8398 | No |
| ETHUSD | USD | 24 observations | LSTM | 248.1003 | 243.6568 | No |
| HDFCBANK | INR | 1 observations | Last-price baseline | 9.6586 | 9.6586 | No |
| HDFCBANK | INR | 5 observations | Last-price baseline | 22.1536 | 22.1536 | No |
| ICICIBANK | INR | 1 observations | Last-price baseline | 14.5166 | 14.5166 | No |
| ICICIBANK | INR | 5 observations | Last-price baseline | 34.8873 | 34.8873 | No |
| INFY | INR | 1 observations | LSTM | 18.4220 | 18.4514 | Yes |
| INFY | INR | 5 observations | Last-price baseline | 41.8088 | 41.8088 | No |
| ITC | INR | 1 observations | Last-price baseline | 2.8715 | 2.8715 | No |
| ITC | INR | 5 observations | Last-price baseline | 6.3395 | 6.3395 | No |
| LT | INR | 1 observations | Last-price baseline | 48.8099 | 48.8099 | No |
| LT | INR | 5 observations | LSTM | 126.8830 | 116.4077 | No |
| MARUTI | INR | 1 observations | Last-price baseline | 163.4751 | 163.4751 | No |
| MARUTI | INR | 5 observations | Last-price baseline | 394.7182 | 394.7182 | No |
| MF119598 | INR | 21 observations | LSTM | 3.6704 | 3.2145 | No |
| MF120503 | INR | 21 observations | LSTM | 4.1086 | 3.9140 | No |
| MF120716 | INR | 21 observations | LSTM | 6.0376 | 5.5697 | No |
| NIFTY50 | INR | 1 observations | LSTM | 177.6048 | 176.9530 | No |
| NIFTY50 | INR | 5 observations | LSTM | 425.4082 | 418.8167 | No |
| RELIANCE | INR | 1 observations | Last-price baseline | 14.8414 | 14.8414 | No |
| RELIANCE | INR | 5 observations | LSTM | 34.5012 | 33.2359 | No |
| RELIANCE_5m | INR | 3 observations | LSTM | 2.4959 | 2.4831 | No |
| SBIN | INR | 1 observations | LSTM | 12.4028 | 12.0635 | No |
| SBIN | INR | 5 observations | LSTM | 29.6856 | 27.3105 | No |
| SENSEX | INR | 1 observations | LSTM | 588.6810 | 586.5518 | No |
| SENSEX | INR | 5 observations | LSTM | 1392.4612 | 1375.9607 | No |
| SOLUSDT | USDT | 1 observations | Last-price baseline | 1.8801 | 1.8801 | No |
| SOLUSDT_1h | USDT | 1 observations | Last-price baseline | 0.3738 | 0.3738 | No |
| SOLUSDT_1h | USDT | 24 observations | Last-price baseline | 1.8663 | 1.8663 | No |
| SOLUSDT | USDT | 24 observations | Moving-average baseline | 13.5663 | 13.1455 | No |
| SOLUSD | USD | 1 observations | LSTM | 1.9713 | 1.8884 | No |
| SOLUSD | USD | 24 observations | Gradient boosting | 18.8095 | 10.9496 | No |
| SUNPHARMA | INR | 1 observations | Last-price baseline | 16.4039 | 16.4039 | No |
| SUNPHARMA | INR | 5 observations | Last-price baseline | 37.5287 | 37.5287 | No |
| TATASTEEL | INR | 1 observations | Last-price baseline | 2.3715 | 2.3715 | No |
| TATASTEEL | INR | 5 observations | LSTM | 4.7649 | 4.7331 | No |
| TCS | INR | 1 observations | Last-price baseline | 33.6492 | 33.6492 | No |
| TCS | INR | 5 observations | Last-price baseline | 79.6309 | 79.6309 | No |
| TCS_5m | INR | 3 observations | Last-price baseline | 5.4122 | 5.4122 | No |

MAE is mean absolute price error. The baseline predicts that the future close equals the latest visible close. These experiments do not establish profitable future trading. Full provenance, test plots, and strategy assumptions are available in Model lab.

The source data excludes unfinished daily bars. Each report contains its dataset checksum, seed, library versions, and dated partitions.
