from abc import ABC, abstractmethod

class ExchangeClient(ABC):
    @abstractmethod
    def get_price(self, symbol: str) -> dict:
        """
        지정한 종목의 현재가, 전일대비 변동률 등을 조회합니다.
        반환값:
            dict: { "current_price": float, "change_rate": float, "raw": dict }
        """
        pass

    @abstractmethod
    def get_balance(self) -> dict:
        """
        총 평가금액, 가용 예수금 및 현재 보유 중인 자산 목록을 조회합니다.
        반환값:
            dict: {
                "total_evaluation": float,
                "available_cash": float,
                "holdings": list of dict (symbol, name, qty, avg_price, current_price, profit, profit_rate)
            }
        """
        pass

    @abstractmethod
    def place_order(self, symbol: str, qty: float, side: str, ord_type: str, price: float = None) -> dict:
        """
        매수 또는 매도 주문을 접수합니다.
        반환값:
            dict: { "order_id": str, "status": str, "raw": dict }
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict:
        """
        접수된 주문의 체결 상태를 확인합니다.
        반환값:
            dict: { "order_id": str, "status": str, "qty": float, "executed_qty": float, "raw": dict }
        """
        pass
