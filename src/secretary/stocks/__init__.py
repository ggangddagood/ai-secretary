"""주식 브리핑 파이프라인 패키지.

`secretary.main`(AI 브리핑)과 독립된 파이프라인이다. `state/seen.json`을 읽지도 쓰지도 않는다.
하위 모듈은 여기서 import 하지 않는다 — `config.py`가 `stocks.models`를 쓰므로 순환이 생긴다.
"""
