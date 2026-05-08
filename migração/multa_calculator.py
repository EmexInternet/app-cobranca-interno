from __future__ import annotations

from datetime import datetime
import json
import subprocess

from migração.config import Settings


class MultaCalculator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def calculate(self, *, sale_date: str, cancel_date: str) -> dict:
        normalized_sale_date = self._normalize_date_input(sale_date)
        normalized_cancel_date = self._normalize_date_input(cancel_date)
        payload = {
            "saleDate": normalized_sale_date,
            "cancelDate": normalized_cancel_date,
            "benefitValue": self.settings.multa_benefit_value,
        }
        process = subprocess.run(
            ["node", self.settings.multa_cli_script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=".",
            check=False,
        )
        if process.returncode != 0:
            stderr = (process.stderr or process.stdout or "").strip()
            raise RuntimeError(f"Falha ao calcular multa via Node.js: {stderr}")

        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Resposta invalida do calculo de multa em Node.js.") from exc

        fine_value = float(result.get("fineValue") or 0)
        result["fineValue"] = fine_value
        result["normalizedSaleDate"] = normalized_sale_date
        result["normalizedCancelDate"] = normalized_cancel_date
        return result

    @staticmethod
    def _normalize_date_input(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return normalized

        for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(normalized, date_format).strftime("%Y-%m-%d")
            except ValueError:
                continue

        return normalized
