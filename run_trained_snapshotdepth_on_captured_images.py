"""
Usage

python run_trained_snapshotdepth_on_captured_images.py \
    --scene indoor --captimg_path data/captured_data/indoor2_predemosaic.tif \
    --ckpt_path data/checkpoints/checkpoint.ckpt
"""

import os
from argparse import ArgumentParser
from PIL import Image
import matplotlib.pyplot as plt
import numpy as np
import skimage.io
import torch
from snapshotdepth import SnapshotDepth
from solvers.image_reconstruction import apply_tikhonov_inverse
from util.fft import crop_psf
from util.helper import crop_boundary, linear_to_srgb


def to_uint8(x: torch.Tensor):
    """
    x: B x C x H x W
    """
    return (255 * x.squeeze(0).clamp(0, 1)).permute(1, 2, 0).to(torch.uint8)


def strech_img(x):
    return (x - x.min()) / (x.max() - x.min())


def find_minmax(img, saturation=0.1):
    min_val = np.percentile(img, saturation)
    max_val = np.percentile(img, 100 - saturation)
    return min_val, max_val


def rescale_image(x):
    min, max = find_minmax(x)
    return (x - min) / (max - min)


def average_inference(x):
    x = torch.stack([
        x[0],
        torch.flip(x[1], dims=(-1,)),
        torch.flip(x[2], dims=(-2,)),
        torch.flip(x[3], dims=(-2, -1)),
    ], dim=0)
    return x.mean(dim=0, keepdim=True)


@torch.no_grad()
def main(args):
    device = torch.device('cpu')

    
    # Load the saved checkpoint
    # This is not a default way to load the checkpoint through Lightning.
    # My code cleanup made it difficult to directly load the checkpoint from what I used for the paper.
    # So, manually loading the learnable parameters to the model.
    ckpt = torch.load(args.ckpt_path, map_location=lambda storage, loc: storage)
    hparams = ckpt['hyper_parameters']
    model = SnapshotDepth(hparams=hparams)

    model.camera.heightmap1d_.data = ckpt['state_dict']['camera.heightmap1d_']
    decoder_dict = {key[8:]: value for key, value in ckpt['state_dict'].items() if 'decoder' in key}
    model.decoder.load_state_dict(decoder_dict)
    model.eval()

    save_name = os.path.splitext(os.path.basename(args.captimg_path))[0]
    captimg_linear = torch.from_numpy(np.array(Image.open(args.captimg_path)).astype(np.float32)).unsqueeze(0) / 255.
    print(captimg_linear.shape)

    # add batch dim
    captimg_linear = captimg_linear.permute(0,3,1,2)
    # Debayer with the bilinear interpolation
    # captimg_linear = model.debayer(captimg_linear)

    # captimg_linear /= captimg_linear.max()

    # # Inference-time augmentation
    captimg_linear = torch.cat([
        captimg_linear,
        torch.flip(captimg_linear, dims=(-1,)),
        torch.flip(captimg_linear, dims=(-2,)),
        torch.flip(captimg_linear, dims=(-1, -2)),
    ], dim=0)

    image_sz = captimg_linear.shape[-2:]

    captimg_linear = captimg_linear.to(device)
    model = model.to(device)

    psf = model.camera.normalize_psf(model.camera.psf_at_camera(size=image_sz).unsqueeze(0))
    psf_cropped = crop_psf(psf, image_sz)
    pinv_volumes = apply_tikhonov_inverse(captimg_linear, psf_cropped, model.hparams.reg_tikhonov,
                                          apply_edgetaper=True)
    model_outputs = model.decoder(captimgs=captimg_linear, pinv_volumes=pinv_volumes)

    # est_images = crop_boundary(model_outputs.est_images, model.crop_width)
    # est_depthmaps = crop_boundary(model_outputs.est_depthmaps, model.crop_width)
    # capt_images = linear_to_srgb(crop_boundary(captimg_linear[[0]], model.crop_width))

    # est_images = average_inference(est_images)
    # est_depthmaps = average_inference(est_depthmaps)
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    est_depthmaps = model_outputs.est_depthmaps
    est_depthmaps = average_inference(est_depthmaps)
    print(est_depthmaps.shape)
    scaled_depthmaps = est_depthmaps.squeeze().cpu().numpy() * 5000.0
    # Save the results
    # skimage.io.imsave(f'data/result/{save_name}_captimg.png', to_uint8(rescale_image(capt_images)))
    # skimage.io.imsave(f'data/result/{save_name}_estimg.png', to_uint8(rescale_image(est_images)))
    plt.imsave(f'data/result/{save_name}_estdepthmap.png',scaled_depthmaps.astype(np.uint16))



if __name__ == '__main__':
    parser = ArgumentParser(add_help=False)
    parser.add_argument('--captimg_path', type=str)
    parser.add_argument('--ckpt_path', type=str, default='data/checkpoints/checkpoint.ckpt')

    parser = SnapshotDepth.add_model_specific_args(parser)
    args = parser.parse_args()
    main(args)
