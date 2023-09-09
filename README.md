# dfd
## How to run the training code

```shell
python snapshotdepth_trainer.py \
  --gpus 4 --batch_sz 3 --distributed_backend ddp  --max_epochs 100  --optimize_optics  --psfjitter  --replace_sampler_ddp False
```
## How to run the inference code on a real captured data

Download the captured image and the checkpoint, and place them in `data` directory.

```shell
python run_trained_snapshotdepth_on_captured_images.py \
  --ckpt_path data/checkpoint.ckpt \
  --captimg_path data/captured_data/outdoor1_predemosaic.tif 
```
