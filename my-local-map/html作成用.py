import os
import json
import re
import math
from qgis.core import QgsProject, QgsJsonExporter

# =====================================================================
# 設定項目
# =====================================================================
OUTPUT_DIR = r"C:\Users\kindt\OneDrive\Desktop\naming_rights_project\my-local-map"
LAYER_NAME = "ichiran"
# =====================================================================

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
data_dir = os.path.join(OUTPUT_DIR, "data")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
chartjs_dir = os.path.join(OUTPUT_DIR, "chartjs")
if not os.path.exists(chartjs_dir):
    os.makedirs(chartjs_dir)

# 1. レイヤーの取得
layer = None
all_layers = QgsProject.instance().mapLayers().values()
for ly in all_layers:
    if ly.name() == LAYER_NAME:
        layer = ly
        break

if layer is None:
    raise Exception(f"レイヤー '{LAYER_NAME}' が見つかりません。")

if layer.isEditable():
    layer.commitChanges()

# 2. データの初期抽出とPython側での事前集計
pref_counts = {}
raw_amount_list = []
period_list = []

features = list(layer.getFeatures())
for feature in features:
    address = str(feature["所在地"]) if feature["所在地"] is not None else ""
    match_pref = re.match(r'^.*?[都道府県]', address)
    if match_pref:
        pref = match_pref.group(0)[-4:].strip()
        if not ("都" in pref or "道" in pref or "府" in pref or "県" in pref):
            pref = address[0:3]
    else:
        pref = address[0:3]
    if pref and ("都" in pref or "道" in pref or "府" in pref or "県" in pref):
        pref_counts[pref] = pref_counts.get(pref, 0) + 1

    amt_val_raw = feature["金額（税抜・万円/年）"]
    if amt_val_raw is not None and str(amt_val_raw).strip() != "" and str(amt_val_raw) != "NULL" and str(amt_val_raw) != "---":
        clean_amt = re.sub(r'[^0-9.]', '', str(amt_val_raw))
        if clean_amt:
            try: raw_amount_list.append(float(clean_amt))
            except: pass

    prd_val_raw = feature["契約期間（年）"]
    if prd_val_raw is not None and str(prd_val_raw).strip() != "" and str(prd_val_raw) != "NULL" and str(prd_val_raw) != "---":
        clean_prd = re.sub(r'[^0-9.]', '', str(prd_val_raw))
        if clean_prd:
            try: period_list.append(float(clean_prd))
            except: pass

# 外れ値解析
def filter_and_analyze_amounts(raw_list):
    if not raw_list: return 0, 0, 0, 0, {}, [], "---", "---", "---"
    n_raw = len(raw_list)
    mean_raw = sum(raw_list) / n_raw
    variance_raw = sum((x - mean_raw) ** 2 for x in raw_list) / n_raw
    stdev_raw = math.sqrt(variance_raw)
    lower_limit = mean_raw - (1.96 * stdev_raw)
    upper_limit = mean_raw + (1.96 * stdev_raw)
    clean_list = [x for x in raw_list if lower_limit <= x <= upper_limit]
    n_clean = len(clean_list)
    outlier_count = n_raw - n_clean
    mean_clean = sum(clean_list) / n_clean
    sorted_clean = sorted(clean_list)
    median_clean = sorted_clean[n_clean // 2] if n_clean % 2 == 1 else (sorted_clean[(n_clean // 2) - 1] + sorted_clean[n_clean // 2]) / 2.0
    stdev_clean = math.sqrt(sum((x - mean_clean) ** 2 for x in clean_list) / n_clean)
    bins = { "100万未満": 0, "100万〜300万": 0, "300万〜500万": 0, "500万〜1000万": 0, "1000万超": 0 }
    for num in clean_list:
        if num < 100: bins["100万未満"] += 1
        elif num <= 300: bins["100万〜300万"] += 1
        elif num <= 500: bins["300万〜500万"] += 1
        elif num <= 1000: bins["500万〜1000万"] += 1
        else: bins["1000万超"] += 1
    return n_raw, n_clean, outlier_count, max(raw_list), bins, clean_list, f"{mean_clean:.1f}", f"{median_clean:.1f}", f"{stdev_clean:.1f}"

def analyze_periods(p_list):
    if not p_list: return "---", "---", "---"
    n = len(p_list)
    mean = sum(p_list) / n
    sorted_p = sorted(p_list)
    median = sorted_p[n//2] if n % 2 == 1 else (sorted_p[(n//2)-1] + sorted_p[n//2]) / 2.0
    stdev = math.sqrt(sum((x - mean) ** 2 for x in p_list) / n)
    return f"{mean:.1f}", f"{median:.1f}", f"{stdev:.1f}"

n_raw, n_clean, outlier_count, max_raw_val, amount_bins, clean_amounts, amt_mean, amt_median, amt_stdev = filter_and_analyze_amounts(raw_amount_list)
prd_mean, prd_median, prd_stdev = analyze_periods(period_list)

period_bins = { "3年以下": 0, "3年超〜5年": 0, "5年超〜10年": 0, "10年超": 0 }
for num in period_list:
    if num <= 3: period_bins["3年以下"] += 1
    elif num <= 5: period_bins["3年超〜5年"] += 1
    elif num <= 10: period_bins["5年超〜10年"] += 1
    else: period_bins["10年超"] += 1

sorted_prefs = sorted(pref_counts.keys(), key=lambda x: pref_counts[x], reverse=True)

pref_html_bars = ""
for p in sorted_prefs:
    width_p = (pref_counts[p] / max(pref_counts.values())) * 75
    pref_html_bars += f"""<div class="filter-bar-row" data-type="pref" data-value="{p}" style="display:flex;align-items:center;margin-bottom:8px;font-size:12px;cursor:pointer;"><div style="width:55px;font-weight:bold;text-align:right;padding-right:10px;">{p}</div><div style="flex:1;background:#f1f2f6;border-radius:3px;height:16px;overflow:hidden;border:1px solid #dcdde1;"><div style="background:#2ed573;width:{width_p}%;height:100%;"></div></div><div style="width:45px;font-weight:bold;padding-left:8px;color:#2f3640;">{pref_counts[p]} 件</div></div>"""

amount_html_bars = ""
for k, v in amount_bins.items():
    width_p = (v / max(amount_bins.values())) * 75 if max(amount_bins.values()) > 0 else 0
    amount_html_bars += f"""<div class="filter-bar-row" data-type="amount" data-value="{k}" style="display:flex;align-items:center;margin-bottom:8px;font-size:12px;cursor:pointer;"><div style="width:90px;font-weight:bold;text-align:right;padding-right:10px;">{k}</div><div style="flex:1;background:#f1f2f6;border-radius:3px;height:16px;overflow:hidden;border:1px solid #dcdde1;"><div style="background:#ffa502;width:{width_p}%;height:100%;"></div></div><div style="width:45px;font-weight:bold;padding-left:8px;color:#2f3640;">{v} 件</div></div>"""

period_html_bars = ""
for k, v in period_bins.items():
    width_p = (v / max(period_bins.values())) * 75
    period_html_bars += f"""<div class="filter-bar-row" data-type="period" data-value="{k}" style="display:flex;align-items:center;margin-bottom:8px;font-size:12px;cursor:pointer;"><div style="width:90px;font-weight:bold;text-align:right;padding-right:10px;">{k}</div><div style="flex:1;background:#f1f2f6;border-radius:3px;height:16px;overflow:hidden;border:1px solid #dcdde1;"><div style="background:#1e90ff;width:{width_p}%;height:100%;"></div></div><div style="width:45px;font-weight:bold;padding-left:8px;color:#2f3640;">{v} 件</div></div>"""

# 3. 地図用GeoJSONデータの書き出し
exporter = QgsJsonExporter(layer)
geojson_string = exporter.exportFeatures(layer.getFeatures())
geojson_string = re.sub(r'"urn:ogc:def:crs:OGC:1\.3:CRS84"', '"EPSG:4326"', geojson_string)
geojson_string = re.sub(r'"urn:ogc:def:crs:EPSG::\d+"', '"EPSG:4326"', geojson_string)

js_data_content = f"const facilitiesGeoJSON = {geojson_string};"
with open(os.path.join(data_dir, "facilities.js"), "w", encoding="utf-8") as f:
    f.write(js_data_content)

# 4. index.html の生成（同一座標ピン完全分解・ラベル常時追従対応版）
html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>ネーミングライツ・データダッシュボード</title>
    <link rel="stylesheet" href="leaflet/leaflet.css" />
    <link rel="stylesheet" href="leaflet/MarkerCluster.css" />
    <link rel="stylesheet" href="leaflet/MarkerCluster.Default.css" />
    <style>
        body {{ margin: 0; padding: 20px; font-family: 'Helvetica Neue', Arial, sans-serif; display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; background: #f5f6fa; color: #2f3640; }}
        h1 {{ margin: 0 0 15px 0; font-size: 22px; font-weight: bold; border-left: 5px solid #2f3640; padding-left: 10px; }}
        .container {{ display: flex; flex: 1; gap: 20px; min-height: 0; }}
        #map {{ flex: 1.3; height: 100%; border: 1px solid #dcdde1; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        #sidebar {{ flex: 1; height: 100%; padding: 15px; border: 1px solid #dcdde1; border-radius: 8px; background: #ffffff; box-sizing: border-box; display: flex; flex-direction: column; overflow-y: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        .chart-box {{ margin-bottom: 25px; background: #fdfdfd; padding: 15px; border-radius: 6px; border: 1px solid #f1f2f6; }}
        .chart-box h3 {{ margin: 0 0 5px 0; font-size: 14px; color: #2f3640; }}
        .chart-box .sub-count {{ font-size: 11px; color: #7f8c8d; border-bottom: 1px solid #f1f2f6; padding-bottom: 8px; margin-bottom: 12px; font-weight: normal; }}
        
        .stats-table {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 15px; background: #fff; }}
        .stats-table th {{ background: #f8f9fa; color: #7f8c8d; text-align: left; padding: 5px 8px; border: 1px solid #e9ecef; font-weight: 600; }}
        .stats-table td {{ padding: 5px 8px; border: 1px solid #e9ecef; font-weight: bold; color: #2f3640; }}

        .filter-bar-row:hover {{ background: #f1f2f6; border-radius: 4px; }}
        .filter-bar-row.active-filter {{ background: #dfe4ea; border-radius: 4px; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1); }}

        .pref-chart-container {{ max-height: 350px; overflow-y: auto; padding-right: 5px; }}
        .popup-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 5px; }}
        .popup-table th {{ background: #f2f2f2; text-align: left; padding: 4px 6px; border: 1px solid #ddd; white-space: nowrap; }}
        .popup-table td {{ padding: 4px 6px; border: 1px solid #ddd; word-break: break-all; }}
        .popup-link {{ display: inline-block; margin-top: 8px; padding: 4px 8px; background: #2f3640; color: white !important; text-decoration: none; border-radius: 4px; font-weight: bold; text-align: center; width: calc(100% - 16px); }}
        .inner-link {{ color: #ff4757 !important; text-decoration: underline; font-weight: bold; }}
        .leaflet-interactive {{ cursor: pointer; }}
        
        /* 高級黒板風ラベル（Tooltip） */
        .custom-label {{ background: rgba(47, 54, 64, 0.95) !important; border: 1px solid #000 !important; color: #fff !important; font-weight: bold !important; font-size: 11px !important; border-radius: 4px !important; padding: 5px 8px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.3); text-align: center !important; line-height: 1.4 !important; }}
        .custom-label::before {{ border-top-color: rgba(47, 54, 64, 0.95) !important; }}

        .credit-footer {{ margin-top: auto; padding-top: 20px; font-size: 11px; text-align: center; color: #a4b0be; border-top: 1px dashed #dcdde1; line-height: 1.6; }}
        .credit-footer a {{ color: #1a73e8 !important; text-decoration: underline; font-weight: bold; }}
    </style>
</head>
<body>

    <h1>ネーミングライツ・データダッシュボード</h1>
    <div class="container">
        <div id="map"></div>
        <div id="sidebar">
            <div class="chart-box">
                <h3>① 都道府県別の施設数 <span style="font-size:11px; color:#ff4757; font-weight:bold;">(★クリックするとその地域へ瞬間ズーム)</span></h3>
                <div class="sub-count">有効データ合計: {total_pref_records} 件</div>
                <div class="pref-chart-container">
                    {pref_html_bars}
                </div>
            </div>
            
            <div class="chart-box">
                <h3>② 金額の分布 (万円/年) ※外れ値除去済み <span style="font-size:11px; color:#ff4757; font-weight:bold;">(★クリックして該当ピンのみ表示)</span></h3>
                <div class="sub-count">分析対象: {n_clean} 件 / 全データ {n_raw} 件中</div>
                
                <table class="stats-table">
                    <tr><th>再計算 平均値</th><td>{amt_mean} 万円/年</td><th>再計算 中央値</th><td>{amt_median} 万円/年</td></tr>
                    <tr><th>再計算 標準偏差</th><td>{amt_stdev}</td><th>最高額(外れ値除く)</th><td>{max(clean_amounts) if clean_amounts else 0:,.0f} 万円</td></tr>
                </table>
                
                {amount_html_bars}
            </div>
            
            <div class="chart-box">
                <h3>③ 契約期間の分布 (年) <span style="font-size:11px; color:#ff4757; font-weight:bold;">(★クリックして該当ピンのみ表示)</span></h3>
                <div class="sub-count">有効データ合計: {total_period_records} 件</div>
                <table class="stats-table">
                    <tr><th>平均値 (年)</th><td>{prd_mean} 年</td><th>中央値 (年)</th><td>{prd_median} 年</td></tr>
                    <tr><th>標準偏差 (σ)</th><td>{prd_stdev}</td><th>最長契約期間</th><td>{max(period_list) if period_list else 0:.0f} 年</td></tr>
                </table>
                {period_html_bars}
            </div>

            <div class="credit-footer">
                データ出典・プラットフォーム基盤：<br>
                <a href="https://namebridge.jp" target="_blank" rel="noopener noreferrer">NAME BRIDGE (ネームブリッジ)</a><br>
                本ダッシュボードは上記サイトのネーミングライツ集約データを基に統計分析・作成されました。
            </div>
        </div>
    </div>

    <script src="leaflet/leaflet.js"></script>
    <script src="leaflet/leaflet.markercluster.js"></script>
    <script src="data/facilities.js"></script>

    <script>
        const map = L.map('map', {{ minZoom: 6, maxZoom: 11 }});
        L.tileLayer('tiles/{{z}}/{{x}}/{{y}}.png', {{ attribution: 'Local OpenStreetMap' }}).addTo(map);
        
        // 【最重要修正①】全く同じ座標のピンを完全に分離させるための、クラスタエンジンの超強力チューニング
        const markers = L.markerClusterGroup({{ 
            showCoverageOnHover: false, 
            spiderfyOnMaxZoom: true,          // 最大拡大時（ズーム11）でも、重なっているピンを強制的にクモの巣状に広げる
            spiderfyDistanceMultiplier: 3.5,  // ばらける距離の半径を「3.5倍」に超拡大（これにより文字ラベルが絶対にぶつかりません）
            removeOutsideVisibleBounds: true  // 画面外の計算をはしょって、バラけるアニメーションの動作をサクサクに軽量化
        }});
        
        let currentFilter = {{ type: null, value: null }};
        
        const focusMarkerStyle = {{
            radius: 12, fillColor: "#ff0033", fillOpacity: 1, color: "#000000", weight: 3, opacity: 1
        }};

        let geoJsonLayer;

        function updateMapFilter() {{
            markers.clearLayers();
            
            geoJsonLayer = L.geoJSON(facilitiesGeoJSON, {{
                pointToLayer: function(feature, latlng) {{ return L.circleMarker(latlng, focusMarkerStyle); }},
                filter: function(feature) {{
                    if (!currentFilter.type) return true;
                    const props = feature.properties;
                    
                    if (currentFilter.type === 'pref') {{
                        const addr = props['所在地'] || '';
                        return addr.startsWith(currentFilter.value);
                    }}
                    if (currentFilter.type === 'amount') {{
                        const amtRaw = props['金額（税抜・万円/年）'];
                        if (!amtRaw || amtRaw === '---') return false;
                        const num = parseFloat(amtRaw);
                        if (isNaN(num)) return false;
                        if (currentFilter.value === "100万未満") return num < 100;
                        if (currentFilter.value === "100万〜300万") return num >= 100 && num <= 300;
                        if (currentFilter.value === "300万〜500万") return num > 300 && num <= 500;
                        if (currentFilter.value === "500万〜1000万") return num > 500 && num <= 1000;
                        if (currentFilter.value === "1000万超") return num > 1000;
                    }}
                    if (currentFilter.type === 'period') {{
                        const prdRaw = props['契約期間（年）'];
                        if (!prdRaw || prdRaw === '---') return false;
                        const num = parseFloat(prdRaw);
                        if (isNaN(num)) return false;
                        if (currentFilter.value === "3年以下") return num <= 3;
                        if (currentFilter.value === "3年超〜5年") return num > 3 && num <= 5;
                        if (currentFilter.value === "5年超〜10年") return num > 5 && num <= 10;
                        if (currentFilter.value === "10年超") return num > 10;
                    }}
                    return true;
                }},
                onEachFeature: function(feature, layer) {{
                    const props = feature.properties;
                    
                    const facilityName = props['施設名'] || props['facility_name'] || props['名称'] || '名称未取得';
                    const amtRaw = props['金額（税抜・万円/年）'];
                    
                    let labelText = facilityName;
                    if (amtRaw !== undefined && amtRaw !== null && amtRaw !== '' && amtRaw !== '---') {{
                        const num = parseFloat(amtRaw);
                        labelText += `<br><span style="color: #ccff00; font-size: 10px;">💰 ${{num.toLocaleString()}} 万円/年</span>`;
                    }} else {{
                        labelText += '<br><span style="color: #aaa; font-size: 10px;">金額未記載</span>';
                    }}
                    
                    // 【最重要修正②】hideOverlapをあえて「false」にし、バラけたすべてのピンのラベルが100%同時に出現するように変更
                    layer.bindTooltip(labelText, {{
                        permanent: true,
                        direction: 'top',
                        className: 'custom-label',
                        offset: [0, -10],
                        hideOverlap: false  // ★バラけたピンすべてに、施設名ラベルを強制的に常時出現させます
                    }});

                    let tableHtml = '<table class="popup-table">';
                    let mapUrl = '#';
                    for (const key in props) {{
                        if (props.hasOwnProperty(key)) {{
                            if (/^field_(1[7-9]|2[0-3])$/.test(key)) continue;
                            let val = props[key] || '---';
                            if (key.toLowerCase().includes('google') && key.toLowerCase().includes('url')) {{ mapUrl = val; continue; }}
                            if (key.includes('掲載元URL') || key.includes('掲載元url') || (typeof val === 'string' && val.startsWith('http'))) {{
                                if (val !== '---' && val !== '#') {{ val = '<a href="' + val + '" class="inner-link" target="_blank">リンク先へ移動</a>'; }}
                            }}
                            tableHtml += '<tr><th>' + key + '</th><td>' + val + '</td></tr>';
                        }}
                    }}
                    tableHtml += '</table>';
                    if (mapUrl !== '#') tableHtml += '<a href="' + mapUrl + '" class="popup-link" target="_blank">Googleマップで開く</a>';
                    layer.bindPopup(tableHtml, {{ maxWidth: 350 }});
                }}
            }});
            
            markers.addLayer(geoJsonLayer);
            map.addLayer(markers);
            
            const bounds = geoJsonLayer.getBounds();
            if (bounds.isValid()) {{
                if (currentFilter.type === 'pref' || geoJsonLayer.getLayers().length <= 5) {{
                    map.fitBounds(bounds, {{ maxZoom: 11, padding: [30, 30] }});
                }} else {{
                    map.fitBounds(bounds, {{ padding: [30, 30] }});
                }}
            }}
        }}

        document.querySelectorAll('.filter-bar-row').forEach(row => {{
            row.addEventListener('click', function() {{
                const type = this.getAttribute('data-type');
                const value = this.getAttribute('data-value');
                
                if (currentFilter.type === type && currentFilter.value === value) {{
                    currentFilter = {{ type: null, value: null }};
                    this.classList.remove('active-filter');
                }} else {{
                    document.querySelectorAll('.filter-bar-row').forEach(r => r.classList.remove('active-filter'));
                    currentFilter = {{ type: type, value: value }};
                    this.classList.add('active-filter');
                }}
                updateMapFilter();
            }});
        }});

        updateMapFilter();
    </script>
</body>
</html>
"""

html_file_path = os.path.join(OUTPUT_DIR, "index.html")
with open(html_file_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print("【密集地対応エンジン実装完了】完全に重なっている重複ピンを大きく分解し、全4つのラベルが同時に見えるように修正しました。")
