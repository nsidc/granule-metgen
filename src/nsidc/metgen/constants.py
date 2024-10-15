DEFAULT_CUMULUS_ENVIRONMENT = 'uat'

GPOLYGON = 'gpolygon'
RECTANGLE = 'rectangle'
POINT = 'point'

UMMG_BODY_TEMPLATE = 'src/nsidc/metgen/templates/ummg_body_template.json'
UMMG_TEMPORAL_TEMPLATE = 'src/nsidc/metgen/templates/ummg_temporal_single_template.json'
UMMG_SPATIAL_GPOLYGON_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_gpolygon_template.json'
UMMG_SPATIAL_POINT_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_point_template.json'
UMMG_SPATIAL_RECTANGLE_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_rectangle_template.json'

UMMG_SINGLE_POINT_TEMPLATE = '{"Longitude": $longitude, "Latitude": $latitude}'

SPATIAL_TEMPLATES = {
    GPOLYGON: UMMG_SPATIAL_GPOLYGON_TEMPLATE,
    POINT: UMMG_SPATIAL_POINT_TEMPLATE,
    RECTANGLE: UMMG_SPATIAL_RECTANGLE_TEMPLATE
}