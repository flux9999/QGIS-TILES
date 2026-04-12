
import os
import json
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY
from qgis.utils import iface
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView

# --- ユーザー設定 --- ここから編集してください ---
# HTMLファイルとLeaflet関連ファイルの出力先ディレクトリ（絶対パスで指定）
# 例: "C:/Users/your_user/Desktop/map_output"
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "qgis_map_output")

# 検索機能とラベル表示の対象となるCSVレイヤーの名前（正確な名前を一つ指定）
CSV_LAYER_NAME = "あなたのCSVレイヤー名"

# 地理院地図タイルのサブフォルダ名 (OUTPUT_DIR/ の下に配置されることを想定)
# 例: "tiles" とした場合、OUTPUT_DIR/tiles/{z}/{x}/{y}.png を読み込みます。
GEOSPATIAL_TILES_SUBDIR = "tiles"
# --- ユーザー設定 --- ここまで ---

LOCAL_TILES_PATH = os.path.join(OUTPUT_DIR, GEOSPATIAL_TILES_SUBDIR)

# 出力ディレクトリが存在しない場合は作成
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
# タイルフォルダも作成（ユーザーがここにタイルを配置することを想定）
if not os.path.exists(LOCAL_TILES_PATH):
    os.makedirs(LOCAL_TILES_PATH)

def export_qgis_to_leaflet():
    project = QgsProject.instance()
    layers = project.mapLayers().values()

    geojson_point_features = []
    geojson_other_features = []

    for layer in layers:
        # 表示されているベクタレイヤーのみを対象
        if layer.type() == QgsVectorLayer.VectorLayer and layer.isVisible():
            for feature in layer.getFeatures():
                geom = feature.geometry()
                properties = feature.attributes()
                field_names = [field.name() for field in layer.fields()]
                
                # 属性を辞書に変換
                props_dict = {}
                for i, field_name in enumerate(field_names):
                    props_dict[field_name] = properties[i]
                
                # レイヤー名を追加（検索機能で利用）
                props_dict["layer_name"] = layer.name()

                feature_geojson = {
                    "type": "Feature",
                    "geometry": json.loads(geom.asJson()), # QgsGeometryをGeoJSON形式に変換
                    "properties": props_dict
                }

                if geom.type() == QgsGeometry.Point: # ポイントレイヤーはクラスター対象
                    geojson_point_features.append(feature_geojson)
                else: # その他のジオメトリタイプは個別のレイヤーとして追加
                    geojson_other_features.append(feature_geojson)

    geojson_point_data = {
        "type": "FeatureCollection",
        "features": geojson_point_features
    }
    geojson_other_data = {
        "type": "FeatureCollection",
        "features": geojson_other_features
    }

    # HTMLテンプレート
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>QGIS Leaflet Map</title>
    <meta charset=\
"utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="leaflet.css" />
    <link rel="stylesheet" href="MarkerCluster.css" />
    <link rel="stylesheet" href="MarkerCluster.Default.css" />
    <link rel="stylesheet" href="leaflet-search.min.css" />
    <script src="leaflet.js"></script>
    <script src="leaflet.markercluster.js"></script>
    <script src="leaflet-search.min.js"></script>
    <style>
        #map { height: 100vh; width: 100vw; }
        .info-popup { max-height: 200px; overflow-y: auto; }
        .my-label { background-color: white; border: 1px solid grey; padding: 2px 5px; border-radius: 3px; white-space: nowrap; }
    </style>
</head>
<body>
    <div id="map"></div>

    <script>
        var map = L.map("map").setView([32.75, 129.87], 13); // 長崎市周辺を初期表示

        // ローカルの地理院地図タイルを読み込む
        L.tileLayer("{GEOSPATIAL_TILES_SUBDIR}/{{z}}/{{x}}/{{y}}.png", {
            maxZoom: 18,
            minZoom: 0,
            attribution: "<a href=\"https://maps.gsi.go.jp/development/ichiran.html\" target=\"_blank\">地理院タイル</a>"
        }).addTo(map);

        var markers = L.markerClusterGroup();

        var geojsonPointFeatures = {json.dumps(geojson_point_data, ensure_ascii=False)};
        var geojsonOtherFeatures = {json.dumps(geojson_other_data, ensure_ascii=False)};

        var csvLayerName = {json.dumps(CSV_LAYER_NAME, ensure_ascii=False)};

        // ポイントレイヤーの処理（クラスター、検索、ラベル）
        L.geoJSON(geojsonPointFeatures, {
            onEachFeature: function (feature, layer) {
                var popupContent = `<div class="info-popup">`;
                for (var key in feature.properties) {
                    popupContent += `<b>${key}:</b> ${feature.properties[key]}<br>`;
                }
                popupContent += `</div>`;
                layer.bindPopup(popupContent);

                // 検索機能のためのデータ準備とラベル表示
                if (feature.properties["layer_name"] === csvLayerName) {
                    // ラベル表示
                    if (feature.properties["長崎駅からの概算距離順"] && feature.properties["所在地"]) {
                        layer.bindTooltip(`${feature.properties["所在地"]} (${feature.properties["長崎駅からの概算距離順"]}m)`, {permanent: true, direction: "right", className: "my-label"}).openTooltip();
                    }
                }
            }
        }).addTo(markers);

        map.addLayer(markers);

        // その他のベクタレイヤーの処理
        L.geoJSON(geojsonOtherFeatures, {
            onEachFeature: function (feature, layer) {
                var popupContent = `<div class="info-popup">`;
                for (var key in feature.properties) {
                    popupContent += `<b>${key}:</b> ${feature.properties[key]}<br>`;
                }
                popupContent += `</div>`;
                layer.bindPopup(popupContent);
            }
        }).addTo(map);

        // 検索コントロールの追加
        var searchControl = new L.Control.Search({
            position:"topright",
            layer: markers, // マーカークラスターグループ全体を検索対象とする
            initial: false,
            zoom: 18,
            marker: false,
            textPlaceholder: "所在地を検索...",
            propertyName: "所在地", // 検索対象の属性名
            filterData: function(text, records) {
                var jsonp = L.Control.Search.prototype._filterData.apply(this, [text, records]);
                var filtered = {};
                for (var key in jsonp) {
                    if (jsonp[key].layer.feature.properties.layer_name === csvLayerName) {
                        filtered[key] = jsonp[key];
                    }
                }
                return filtered;
            }
        });
        map.addControl( searchControl );

    </script>
</body>
</html>
"""

    html_file_path = os.path.join(OUTPUT_DIR, "qgis_map.html")
    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(html_template.replace("{GEOSPATIAL_TILES_SUBDIR}", GEOSPATIAL_TILES_SUBDIR))

    # Leaflet関連ファイルをOUTPUT_DIRにコピー
    leaflet_files = [
        "leaflet.js", "leaflet.css",
        "leaflet.markercluster.js", "MarkerCluster.css", "MarkerCluster.Default.css",
        "leaflet-search.min.js", "leaflet-search.min.css"
    ]
    for f_name in leaflet_files:
        src_path = os.path.join(os.path.dirname(__file__), "leaflet_assets", f_name) # 以前のダウンロード場所を想定
        dst_path = os.path.join(OUTPUT_DIR, f_name)
        if os.path.exists(src_path):
            import shutil
            shutil.copy(src_path, dst_path)
        else:
            iface.messageBar().pushMessage("警告", f"Leafletファイルが見つかりません: {src_path}", level=1)

    iface.messageBar().pushMessage("成功", f"Leafletマップが作成されました: {html_file_path}", level=0)

    # QWebEngineViewでHTMLファイルを開く
    view = QWebEngineView()
    view.setUrl(QUrl.fromLocalFile(html_file_path))
    view.show()

# スクリプトを実行
export_qgis_to_leaflet()
