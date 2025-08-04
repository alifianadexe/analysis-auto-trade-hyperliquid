import httpx
import json
from typing import Dict, List, Optional, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class HyperliquidClient:
    def __init__(self):
        self.base_url = settings.HYPERLIQUID_API_URL
        self.session = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP session"""
        await self.session.aclose()
    
    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get market data for a specific symbol"""
        try:
            url = f"{self.base_url}/info"
            payload = {
                "type": "metaAndAssetCtxs"
            }
            
            response = await self.session.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            # Process and return market data for the specific symbol
            return self._process_market_data(data, symbol)
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None
    
    async def get_all_market_data(self) -> Optional[List[Dict[str, Any]]]:
        """Get market data for all symbols"""
        try:
            url = f"{self.base_url}/info"
            payload = {
                "type": "metaAndAssetCtxs"
            }
            
            response = await self.session.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return self._process_all_market_data(data)
            
        except Exception as e:
            logger.error(f"Error fetching all market data: {e}")
            return None
    
    async def get_user_state(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get user state including positions and balances"""
        try:
            url = f"{self.base_url}/info"
            payload = {
                "type": "clearinghouseState",
                "user": wallet_address
            }
            
            response = await self.session.post(url, json=payload)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching user state for {wallet_address}: {e}")
            return None
    
    async def get_user_fills(self, wallet_address: str) -> Optional[List[Dict[str, Any]]]:
        """Get user's recent fills/trades"""
        try:
            url = f"{self.base_url}/info"
            payload = {
                "type": "userFills",
                "user": wallet_address
            }
            
            response = await self.session.post(url, json=payload)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching user fills for {wallet_address}: {e}")
            return None
    
    async def place_order(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place a new order"""
        try:
            url = f"{self.base_url}/exchange"
            
            response = await self.session.post(url, json=order_data)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def cancel_order(self, cancel_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cancel an existing order"""
        try:
            url = f"{self.base_url}/exchange"
            
            response = await self.session.post(url, json=cancel_data)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return None
    
    def _process_market_data(self, data: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """Process raw market data for a specific symbol"""
        # Implementation depends on Hyperliquid API response structure
        # This is a placeholder that should be updated based on actual API response
        try:
            if "assetCtxs" in data:
                for asset_ctx in data["assetCtxs"]:
                    if asset_ctx.get("coin") == symbol:
                        return {
                            "symbol": symbol,
                            "price": float(asset_ctx.get("markPx", 0)),
                            "funding_rate": float(asset_ctx.get("funding", 0)),
                            "open_interest": float(asset_ctx.get("openInterest", 0)),
                            "volume_24h": float(asset_ctx.get("dayNtlVlm", 0))
                        }
            return None
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
            return None
    
    def _process_all_market_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process raw market data for all symbols"""
        processed_data = []
        try:
            if "assetCtxs" in data:
                for asset_ctx in data["assetCtxs"]:
                    symbol = asset_ctx.get("coin")
                    if symbol:
                        processed_data.append({
                            "symbol": symbol,
                            "price": float(asset_ctx.get("markPx", 0)),
                            "funding_rate": float(asset_ctx.get("funding", 0)),
                            "open_interest": float(asset_ctx.get("openInterest", 0)),
                            "volume_24h": float(asset_ctx.get("dayNtlVlm", 0))
                        })
            return processed_data
        except Exception as e:
            logger.error(f"Error processing all market data: {e}")
            return []

# Global client instance
hyperliquid_client = HyperliquidClient()
