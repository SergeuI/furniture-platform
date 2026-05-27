# =====================================================
# DRAWER BOTTOM ENGINE
# Логіка дна шухляд
# =====================================================


# =====================================================
# DSP BOTTOM
# =====================================================

def calculate_dsp_bottom(

    drawer_width,

    drawer_depth
):

    return {

        "width": (

            drawer_width - 36
        ),

        "depth": (

            drawer_depth
        ),

        "thickness": 18,

        "type": "dsp_18",

        "bottom_offset": 12
    }

def calculate_movento_dsp_bottom(

    drawer_width,

    drawer_depth
):

    return {

        "width": drawer_width,

        "depth": drawer_depth,

        "thickness": 18,

        "type": "dsp_18",

        "bottom_offset": 12,

        "quarter": {

            "enabled": True,

            "depth": 12,

            "height": 2
        }
    }

# =====================================================
# HDF BOTTOM
# =====================================================

def calculate_hdf_bottom(

    drawer_width,

    drawer_depth,

    groove_depth=10
):

    return {

        "width": (

            drawer_width

            - groove_depth * 2
        ),

        "depth": (

            drawer_depth

            - groove_depth * 2
        ),

        "thickness": 3,

        "type": "hdf_3",

        "bottom_offset": 12
    }



def calculate_telescopic_hdf_bottom(

    inside_width,
    drawer_depth
):

    return {

        "type": "hdf_3",

        "thickness": 3,

        "width": inside_width,

        "depth": drawer_depth
    }


def calculate_tandem_hdf_bottom(

    inside_width,
    drawer_depth
):

    groove_depth = 8

    return {

        "type": "hdf_3",

        "thickness": 3,

        "width":
            inside_width - groove_depth * 2,

        "depth":
            drawer_depth - groove_depth * 2,

        "bottom_offset": 12
    }


def calculate_movento_hdf_bottom(

    inside_width,
    drawer_depth
):

    groove_depth = 8

    return {

        "type": "hdf_3",

        "thickness": 3,

        "width":
            inside_width - groove_depth * 2,

        "depth":
            drawer_depth - groove_depth * 2,

        "bottom_offset": 12,

        "quarter": {

            "enabled": True,

            "depth": 12,

            "height": 2
        }
    }