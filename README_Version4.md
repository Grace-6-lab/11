```markdown
生成城市影响范围变化图 — 说明

目标
- 为每个城市生成两种 PNG：
  1) AEQD_km: 以城市为中心的 Azimuthal Equidistant 投影，缓冲半径以 km 为单位（更准确地表示实际地面距离）。
  2) Mercator_m: 使用 EPSG:3857（网页墨卡托），缓冲半径以 m 为单位（用于对比，注意高纬度存在形变）。

文件结构（示例）:
- data/
  - distances.csv      # 距离数据（见示例格式）
  - city_coords.csv    # 城市经纬度（经度 lon，纬度 lat）
- scripts/
  - plot_influence_maps_both.py
- output_maps/         # 脚本运行后在此生成 PNG 文件

依赖（建议使用 conda）:
  conda create -n mapenv python=3.10 geopandas -c conda-forge
  conda activate mapenv
  pip install matplotlib pyproj pandas

运行（本地）:
  python scripts/plot_influence_maps_both.py

自动化（GitHub Actions）:
- workflows/generate_maps.yml 会在 push 到 add-influence-maps 分支时运行脚本并把生成的图片提交回该分支。

说明:
- 脚本默认按 distances.csv 中的 target 字段作为“影响中心”统计。每年取所有 source 对 target 的最大距离作为该年影响半径。
- AEQD 圆在投影中以米为单位计算（脚本在内部把 km->m 并用以城市为中心的 aeqd 投影缓冲，然后再投回 EPSG:4326 绘图）。
- Mercator 图在 EPSG:3857 中直接以米缓冲（用于对比效果，注意扭曲）。
```