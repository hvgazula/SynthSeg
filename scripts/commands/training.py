import ast
import glob
import json
import os
import sys

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 

from argparse import ArgumentParser
from SynthSeg.training import training
from ext.lab2im.utils import infer
from scripts.photos_utils import write_config

parser = ArgumentParser()
subparsers = parser.add_subparsers(help='sub-command help')

# create the parser for the "resume-train" command
parser_a = subparsers.add_parser('resume-train', help='Use this sub-command for resuming training')
parser_a.add_argument('checkpoint_folder', type=str, help='''Folder containing previous checkpoints
Must contain either w2l_*.h5 or dice_*.h5''')

# create the parser for the "train" command
parser_b = subparsers.add_parser('train', help='Use this sub-command for training')
# ------------------------------------------------- General parameters -------------------------------------------------
# Positional arguments
parser_b.add_argument("labels_dir", type=str)
parser_b.add_argument("model_dir", type=str)

# ---------------------------------------------- Generation parameters ----------------------------------------------
# label maps parameters
parser_b.add_argument("--generation_labels", type=str, dest="generation_labels", default=None)
parser_b.add_argument("--segmentation_labels", type=str, dest="segmentation_labels", default=None)
parser_b.add_argument("--noisy_patches", nargs='?', type=str, dest="patch_dir", default=None)

# output-related parameters
parser_b.add_argument("--batch_size", type=int, dest="batchsize", default=1)
parser_b.add_argument("--channels", type=int, dest="n_channels", default=1)
parser_b.add_argument("--target_res", nargs='?', type=float, dest="target_res", default=None)
parser_b.add_argument("--output_shape", type=int, dest="output_shape", default=None)

# GMM-sampling parameters
parser_b.add_argument("--generation_classes", type=str, dest="generation_classes", default=None)
parser_b.add_argument("--prior_type", type=str, dest="prior_distributions", default='uniform')
parser_b.add_argument("--prior_means", nargs='?', type=infer, dest="prior_means", default=None)
parser_b.add_argument("--prior_stds", nargs='?', type=infer, dest="prior_stds", default=None)
parser_b.add_argument("--specific_stats", action='store_true', dest="use_specific_stats_for_channel")
parser_b.add_argument("--mix_prior_and_random", action='store_true', dest="mix_prior_and_random")

# spatial deformation parameters
parser_b.add_argument("--no_flipping", action='store_false', dest="flipping")
parser_b.add_argument("--scaling", nargs='?', dest="scaling_bounds", type=infer, default=0.15)
parser_b.add_argument("--rotation", nargs='?', dest="rotation_bounds", type=infer, default=15)
parser_b.add_argument("--shearing", nargs='?', dest="shearing_bounds", type=infer, default=.012)
parser_b.add_argument("--translation", nargs='?', dest="translation_bounds", type=infer, default=False)
parser_b.add_argument("--nonlin_std", type=infer, dest="nonlin_std", default=3.)
parser_b.add_argument("--nonlin_shape_factor", type=infer, dest="nonlin_shape_factor", default=.04)

# blurring/resampling parameters
parser_b.add_argument("--randomise_res", action='store_true', dest="randomise_res")
parser_b.add_argument("--max_res_iso", type=float, dest="max_res_iso", default=4.)
parser_b.add_argument("--max_res_aniso", type=float, dest="max_res_aniso", default=8.)
parser_b.add_argument("--data_res", dest="data_res", type=infer, default=None)
parser_b.add_argument("--thickness", dest="thickness", type=infer, default=None)
parser_b.add_argument("--downsample", action='store_true', dest="downsample")
parser_b.add_argument("--blur_range", type=float, dest="blur_range", default=1.03)

# bias field parameters
parser_b.add_argument("--bias_std", type=float, dest="bias_field_std", default=.5)
parser_b.add_argument("--bias_shape_factor", type=infer, dest="bias_shape_factor", default=.025)
parser_b.add_argument("--same_bias_for_all_channels", action='store_true', dest="same_bias_for_all_channels")

# -------------------------------------------- UNet architecture parameters --------------------------------------------
parser_b.add_argument("--n_levels", type=int, dest="n_levels", default=5)
parser_b.add_argument("--conv_per_level", type=int, dest="nb_conv_per_level", default=2)
parser_b.add_argument("--conv_size", type=int, dest="conv_size", default=3)
parser_b.add_argument("--unet_feat", type=int, dest="unet_feat_count", default=24)
parser_b.add_argument("--feat_mult", type=int, dest="feat_multiplier", default=2)
parser_b.add_argument("--activation", type=str, dest="activation", default='elu')

# ------------------------------------------------- Training parameters ------------------------------------------------
parser_b.add_argument("--lr", type=float, dest="lr", default=1e-4)
parser_b.add_argument("--lr_decay", type=float, dest="lr_decay", default=0)
parser_b.add_argument("--wl2_epochs", type=int, dest="wl2_epochs", default=5)
parser_b.add_argument("--dice_epochs", type=int, dest="dice_epochs", default=100)
parser_b.add_argument("--steps_per_epoch", type=int, dest="steps_per_epoch", default=1000)
parser_b.add_argument("--checkpoint", type=str, dest="checkpoint", default=None)

parser_b.add_argument("--message", type=str, dest="message", default=None)

# import sys
# sys.argv = ['/autofs/space/calico_001/users/Harsha/SynthSeg/scripts/commands/training.py',
#  '/space/calico/1/users/Harsha/SynthSeg/data/SynthSeg_label_maps_manual_auto_photos_noCerebellumOrBrainstem',
#  '/space/calico/1/users/Harsha/SynthSeg/models',
#  '--generation_labels',
#  '/autofs/space/calico_001/users/Harsha/SynthSeg/data/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/generation_charm_choroid_lesions.npy',
#  '--segmentation_labels',
#  '/autofs/space/calico_001/users/Harsha/SynthSeg/data/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/segmentation_new_charm_choroid_lesions.npy',
#  '--noisy_patches',
#  '--batch_size',
#  '1',
#  '--channels',
#  '3',
#  '--target_res',
#  '--output_shape',
#  '96',
#  '--generation_classes',
#  '/autofs/space/calico_001/users/Harsha/SynthSeg/data/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/generation_classes_charm_choroid_lesions_gm.npy',
#  '--prior_type',
#  'uniform',
#  '--prior_means',
#  '--prior_std',
#  '--no_flipping',
#  '--scaling',
#  '--rotation',
#  '--shearing',
#  '--translation',
#  '--nonlin_std',
#  '(4, 0, 4)',
#  '--nonlin_shape_factor',
#  '(0.0625, 0.25, 0.0625)',
#  '--data_res',
#  '(1, 4, 1)',
#  '--thickness',
#  '(1, 0.001,1)',
#  '--downsample',
#  '--blur_range',
#  '1.03',
#  '--bias_std',
#  '.5',
#  '--bias_shape_factor',
#  '(0.025, 0.25, 0.025)',
#  '--n_levels',
#  '5',
#  '--conv_per_level',
#  '2',
#  '--conv_size',
#  '3',
#  '--unet_feat',
#  '24',
#  '--feat_mult',
#  '2',
#  '--activation',
#  'elu',
#  '--lr',
#  '1e-4',
#  '--lr_decay',
#  '0',
#  '--wl2_epochs',
#  '1',
#  '--dice_epochs',
#  '100',
#  '--steps_per_epoch',
#  '5000']

args = parser.parse_args()

if sys.argv[1] == 'train':

    try:
        args.data_res = ast.literal_eval(args.data_res)
    except ValueError:
        pass
    try:
        args.thickness = ast.literal_eval(args.thickness)
    except ValueError:
        pass
    try:
        args.bias_shape_factor = ast.literal_eval(args.bias_shape_factor)
    except ValueError:
        pass
    try:
        args.nonlin_shape_factor = ast.literal_eval(args.nonlin_shape_factor)
    except ValueError:
        pass
    try:
        args.nonlin_std = ast.literal_eval(args.nonlin_std)
    except ValueError:
        pass

    if os.environ.get('SLURM_JOBID'):
        base_path, model_dir_name = os.path.split(args.model_dir)
        model_dir_name = model_dir_name + '-' + os.environ.get('SLURM_JOBID')
        args.model_dir = os.path.join(base_path, model_dir_name)

    write_config(vars(args))
    delattr(args, 'message')

    training(**vars(args))

elif sys.argv[1] == 'resume-train':
    chkpt_folder = args.checkpoint_folder

    config_file = os.path.join(chkpt_folder, 'config.json')
    assert os.path.exists(config_file), 'Configuration file not found'

    with open(config_file) as json_file:
        data = json.load(json_file)

    assert isinstance(data, dict), 'Invalid Object Type'

    data.pop('message', 'Key Error')
    
    dice_list = sorted(glob.glob(os.path.join(chkpt_folder, 'dice*.h5')))
    wl2_list = sorted(glob.glob(os.path.join(chkpt_folder, 'wl2*.h5')))

    print(dice_list)
    print(wl2_list)

    if dice_list:
        data['checkpoint'] = dice_list[-1]
    elif wl2_list:
        data['checkpoint'] = wl2_list[-1]
    else:
        sys.exit('No checkpoints exist to resume training')

    print(data)
    training(**data)

else:
    raise Exception('Invalid Sub-command')
