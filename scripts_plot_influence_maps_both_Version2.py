#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为每个城市生成两类影响范围变化图（AEQD_km 与 Mercator_m）。
输出:
  output_maps/<city>_AEQD_km.png
  output_maps/<city>_Mercator_m.png

依赖:
  conda/mamba 推荐: geopandas matplotlib pyproj pandas shapely fiona rasterio
  pip 可选安装: pandas matplotlib pyproj shapely geopandas fiona rasterio
"""
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
from pyproj import CRS, Transformer

DATA_DIR = "data"
OUT_DIR = "output_maps"
DIST_CSV = os.path.join(DATA_DIR, "distances.csv")
COORD_CSV = os.path.join(DATA_DIR, "city_coords.csv")
YEARS = ["2000", "2005", "2010", "2015", "2019"]
YEAR_COLORS = {
    "2000": "#1f77b4",
    "2005": "#ff7f0e",
    "2010": "#2ca02c",
    "2015": "#d62728",
    "2019": "#9467bd",
}
ALPHAS = {"2000": 0.25, "2005": 0.25, "2010": 0.25, "2015": 0.25, "2019": 0.40}

os.makedirs(OUT_DIR, exist_ok=True)

# 读取数据
df = pd.read_csv(DIST_CSV, dtype=str)
for y in YEARS:
    df[y] = pd.to_numeric(df[y], errors="coerce")

coords = pd.read_csv(COORD_CSV)
gdf_cities = gpd.GeoDataFrame(coords, geometry=[Point(xy) for xy in zip(coords['lon'], coords['lat'])], crs="EPSG:4326")

# 底图：中国
world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
china = world[world["name"] == "China"].to_crs("EPSG:4326")

def make_aeqd_crs(lat, lon):
    return CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")

def generate_for_city(target_city):
    row = gdf_cities[gdf_cities['city'] == target_city]
    if row.empty:
        print(f"[WARN] 未找到坐标：{target_city}")
        return
    lon = float(row.geometry.x.values[0])
    lat = float(row.geometry.y.values[0])

    sub = df[df['target'] == target_city]
    if sub.empty:
        sub = df[df['source'] == target_city]
        if sub.empty:
            print(f"[WARN] 数据中没有 {target_city} 的记录，跳过。")
            return
        else:
            print(f"[INFO] 使用 source=={target_city} 的记录代替 target。")

    # 聚合：每年取最大值作为影响半径（km）
    radii_km = {}
    for y in YEARS:
        vals = sub[y].dropna().values
        radii_km[y] = float(vals.max()) if vals.size > 0 else 0.0

    # AEQD: 在以城市为中心的投影中以米缓冲
    aeqd = make_aeqd_crs(lat, lon)
    tf_to_aeqd = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True)
    tf_to_wgs84 = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True)
    x_m, y_m = tf_to_aeqd.transform(lon, lat)

    from shapely.ops import transform as shp_transform
    import shapely.geometry as geom

    aeqd_polys = {}
    for y, r_km in radii_km.items():
        r_m = r_km * 1000.0
        if r_m <= 0:
            aeqd_polys[y] = None
            continue
        circ = geom.Point(x_m, y_m).buffer(r_m, resolution=128)
        def proj_fun(xx, yy, zz=None):
            return tf_to_wgs84.transform(xx, yy)
        aeqd_polys[y] = shp_transform(proj_fun, circ)

    # 绘图 AEQD
    fig, ax = plt.subplots(figsize=(8, 10))
    china.plot(ax=ax, color="#f0f0f0", edgecolor="#555555")
    for y in YEARS:
        poly = aeqd_polys.get(y)
        if poly is None:
            continue
        gpd.GeoSeries([poly], crs="EPSG:4326").plot(ax=ax, facecolor=YEAR_COLORS[y], alpha=ALPHAS[y], edgecolor=None)
    gdf_cities.plot(ax=ax, color="black", markersize=20, zorder=5)
    for i, r in gdf_cities.iterrows():
        ax.annotate(r["city"], xy=(r.geometry.x + 0.25, r.geometry.y + 0.25), fontsize=9, zorder=6)
    from matplotlib.patches import Patch
    legend_patches = [Patch(facecolor=YEAR_COLORS[y], alpha=ALPHAS[y], label=y) for y in YEARS]
    ax.legend(handles=legend_patches, title="年份", loc="lower left")
    ax.set_title(f"{target_city} 影响范围变化（AEQD - 半径单位: km）")
    ax.set_xlabel("经度"); ax.set_ylabel("纬度")

    max_km = max(radii_km.values()) if radii_km else 0
    if max_km > 0:
        max_m = max_km * 1000.0 * 1.2
        corners = [(x_m - max_m, y_m - max_m), (x_m + max_m, y_m + max_m)]
        lonlat = [tf_to_wgs84.transform(xc, yc) for xc, yc in corners]
        lons = [c[0] for c in lonlat]; lats = [c[1] for c in lonlat]
        ax.set_xlim(min(lons), max(lons)); ax.set_ylim(min(lats), max(lats))

    outpath = os.path.join(OUT_DIR, f"{target_city}_AEQD_km.png")
    plt.tight_layout(); plt.savefig(outpath, dpi=300); plt.close(fig)
    print(f"[OK] AEQD 图已保存: {outpath}")

    # Mercator (EPSG:3857) 以 m 缓冲（对比）
    merc_crs = CRS.from_epsg(3857)
    tf_to_3857 = Transformer.from_crs("EPSG:4326", merc_crs, always_xy=True)
    tf_to_wgs84_3857 = Transformer.from_crs(merc_crs, "EPSG:4326", always_xy=True)
    x3857, y3857 = tf_to_3857.transform(lon, lat)

    merc_polys = {}
    for y, r_km in radii_km.items():
        r_m = r_km * 1000.0
        if r_m <= 0:
            merc_polys[y] = None
            continue
        circ = geom.Point(x3857, y3857).buffer(r_m, resolution=128)
        def proj_back(xx, yy, zz=None):
            return tf_to_wgs84_3857.transform(xx, yy)
        merc_polys[y] = shp_transform(proj_back, circ)

    fig, ax = plt.subplots(figsize=(8, 10))
    china.plot(ax=ax, color="#f0f0f0", edgecolor="#555555")
    for y in YEARS:
        poly = merc_polys.get(y)
        if poly is None:
            continue
        gpd.GeoSeries([poly], crs="EPSG:4326").plot(ax=ax, facecolor=YEAR_COLORS[y], alpha=ALPHAS[y], edgecolor=None)
    gdf_cities.plot(ax=ax, color="black", markersize=20, zorder=5)
    for i, r in gdf_cities.iterrows():
        ax.annotate(r["city"], xy=(r.geometry.x + 0.25, r.geometry.y + 0.25), fontsize=9, zorder=6)
    ax.legend(handles=legend_patches, title="年份", loc="lower left")
    ax.set_title(f"{target_city} 影响范围变化（Mercator - 半径单位: m）")
    ax.set_xlabel("经度"); ax.set_ylabel("纬度")

    if max_km > 0:
        max_m = max_km * 1000.0 * 1.2
        corners = [(x3857 - max_m, y3857 - max_m), (x3857 + max_m, y3857 + max_m)]
        lonlat = [tf_to_wgs84_3857.transform(xc, yc) for xc, yc in corners]
        lons = [c[0] for c in lonlat]; lats = [c[1] for c in lonlat]
        ax.set_xlim(min(lons), max(lons)); ax.set_ylim(min(lats), max(lats))

    outpath2 = os.path.join(OUT_DIR, f"{target_city}_Mercator_m.png")
    plt.tight_layout(); plt.savefig(outpath2, dpi=300); plt.close(fig)
    print(f"[OK] Mercator 图已保存: {outpath2}")

if __name__ == "__main__":
    cities = gdf_cities['city'].tolist()
    for c in cities:
        generate_for_city(c)
    print("全部完成，输出目录:", OUT_DIR)