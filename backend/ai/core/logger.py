import logging
import sys
import os

# ===================================================================
# 1. 로깅 기본 설정
# ===================================================================

# 로그 레벨 정의: 개발 시에는 DEBUG, 운영 시에는 INFO 이상으로 설정
LOG_LEVEL = logging.DEBUG if os.getenv('APP_ENV') == 'development' else logging.INFO

# 로거 인스턴스 생성
logger = logging.getLogger('check_and_go_ai')
logger.setLevel(LOG_LEVEL)

# 이미 핸들러가 설정되어 있다면 다시 설정하지 않도록 방지
if not logger.handlers:
    # 2. 콘솔 핸들러 설정 (표준 출력)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)

    # 3. 로그 형식 정의
    # [시간] [로그레벨] [파일:라인] - 메시지
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s'
    )
    console_handler.setFormatter(formatter)

    # 4. 핸들러를 로거에 추가
    logger.addHandler(console_handler)

def log_error(message: str, exc: Optional[Exception] = None):
    """오류 레벨 로깅을 위한 헬퍼 함수"""
    if exc:
        logger.error(f"{message}: {exc}", exc_info=True)
    else:
        logger.error(message)

def log_info(message: str):
    """정보 레벨 로깅을 위한 헬퍼 함수"""
    logger.info(message)

def log_debug(message: str):
    """디버그 레벨 로깅을 위한 헬퍼 함수"""
    logger.debug(message)

# -------------------------------------------------------------------
# 사용 예시:
# from core.logger import logger
# logger.info("Server started successfully.")
# logger.error("API failed", exc=e) 
# -------------------------------------------------------------------