# PartScope Japanese catalogue exporter

This is the first offline conversion milestone. It converts normalized CatCar JSON into static PartScope shards.

The converter will allow only validated Japanese makes (Toyota and Nissan), keep factory OEM rows in `factory_parts`, keep `analogs` empty, and not invent physical dimensions. Hotspot coordinates will remain out of the app output until image-coordinate calibration is verified.

The output format is `data/{first2}.json`, with each shard an object keyed by cleaned SKU. The exporter must refuse a non-empty output directory and enforce the 2 MiB shard budget.

This tool does not crawl or download source pages or images.