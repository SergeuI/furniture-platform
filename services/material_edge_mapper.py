from services.material_edges_map import MATERIAL_EDGE_MAP


# =====================================================
# GET EDGE ARTICLES
# =====================================================

def get_edges_for_material(article):

    return MATERIAL_EDGE_MAP.get(article)