# =====================================================
# PRODUCTION MODEL
# Виробництво
# =====================================================

from dataclasses import dataclass


# =====================================================
# PRODUCTION TRACKING
# Tracking виробництва
# =====================================================

@dataclass
class ProductionTracking:

    part_id: str

    barcode: str

    stage: str

    operator: str = ""

    def to_dict(self):

        return {

            "part_id": self.part_id,

            "barcode": self.barcode,

            "stage": self.stage,

            "operator": self.operator
        }