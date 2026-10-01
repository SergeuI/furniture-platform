import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from api.routes.catalog import _serialize_fitting_detail
from database.base import Base
from database.models.fitting import FittingModel, FittingProductModel, FittingSupplierOfferModel, SupplierModel
from database.models.fitting_3d_asset import Fitting3DAssetModel, Fitting3DAssetSourceModel
from database.models import hole_library  # noqa: F401 - register fitting relationships


class Fitting3DAssetFoundationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(
            self.engine,
            tables=[FittingProductModel.__table__, SupplierModel.__table__, FittingModel.__table__, FittingSupplierOfferModel.__table__, Fitting3DAssetModel.__table__, Fitting3DAssetSourceModel.__table__],
        )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[Fitting3DAssetSourceModel.__table__, Fitting3DAssetModel.__table__, FittingSupplierOfferModel.__table__, FittingModel.__table__, SupplierModel.__table__, FittingProductModel.__table__],
        )
        self.engine.dispose()

    def test_detail_without_asset_returns_null(self):
        with self.Session() as session:
            fitting = FittingModel(name="Confirmat", article="190106")
            session.add(fitting)
            session.commit()
            with patch("api.routes.catalog.list_fitting_supplier_offers", return_value=[]):
                payload = _serialize_fitting_detail(fitting)
            self.assertIsNone(payload["three_d_asset"])

    def test_detail_returns_metadata_and_sources_in_order(self):
        with self.Session() as session:
            fitting = FittingModel(name="Confirmat", article="190106")
            asset = Fitting3DAssetModel(
                status="validated", canonical_format="glb", canonical_file_url="/assets/confirmat.glb",
                canonical_file_size=1234, canonical_sha256="a" * 64, units="mm",
                dimensions_x=7.0, dimensions_y=50.0, dimensions_z=7.0,
                bbox_min_x=-3.5, bbox_min_y=0.0, bbox_min_z=-3.5,
                bbox_max_x=3.5, bbox_max_y=50.0, bbox_max_z=3.5,
                axis_up="Z", axis_forward="Y", origin_x=0.0, origin_y=0.0, origin_z=0.0,
            )
            asset.sources = [
                Fitting3DAssetSourceModel(file_role="material", file_format="mtl", file_name="confirmat.mtl", order_index=20),
                Fitting3DAssetSourceModel(file_role="model", file_format="obj", file_name="confirmat.obj", order_index=10),
            ]
            fitting.three_d_asset = asset
            session.add(fitting)
            session.commit()
            session.expire_all()
            fitting = session.get(FittingModel, fitting.id)
            with patch("api.routes.catalog.list_fitting_supplier_offers", return_value=[]):
                payload = _serialize_fitting_detail(fitting)["three_d_asset"]
            self.assertEqual(payload["status"], "validated")
            self.assertEqual(payload["canonical_format"], "glb")
            self.assertEqual(payload["dimensions_y"], 50.0)
            self.assertEqual(payload["axis_forward"], "Y")
            self.assertEqual([source["order_index"] for source in payload["sources"]], [10, 20])

    def test_unique_fitting_and_cascade_delete(self):
        with self.Session() as session:
            fitting = FittingModel(name="Confirmat")
            session.add(fitting)
            session.flush()
            first = Fitting3DAssetModel(fitting_id=fitting.id)
            first.sources = [Fitting3DAssetSourceModel(file_role="model", file_format="obj", file_name="x.obj")]
            session.add(first)
            session.commit()
            session.add(Fitting3DAssetModel(fitting_id=fitting.id))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()
            session.delete(first)
            session.commit()
            self.assertEqual(session.query(Fitting3DAssetSourceModel).count(), 0)


if __name__ == "__main__":
    unittest.main()
