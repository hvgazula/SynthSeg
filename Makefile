# Run all commands in one shell
.ONESHELL:

# Default target
.DEFAULT_GOAL := help

# Generic Variables
USR := $(shell whoami | head -c 2)
DT := $(shell date +"%Y%m%d")

PROJ_DIR := $(shell pwd)
DATA_DIR := $(PROJ_DIR)/data
CMD = sbatch submit.sh
# {echo | python | sbatch submit.sh}

ACTIVATE_ENV = source /space/calico/1/users/Harsha/synthseg-venv/bin/activate

# variables for SynthSeg
labels_dir = /space/calico/1/users/Harsha/SynthSeg/data/SynthSeg_label_maps_manual_auto_photos_noCerebellumOrBrainstem
model_dir = /cluster/scratch/friday/for_harsha/$(DT)

## label maps parameters ##
generation_labels = $(DATA_DIR)/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/generation_charm_choroid_lesions.npy
segmentation_labels = $(DATA_DIR)/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/segmentation_new_charm_choroid_lesions.npy
noisy_patches =

## output-related parameters ##
batch_size = 1
channels = 3
target_res =
output_shape = 192

# GMM-sampling parameters
generation_classes = $(DATA_DIR)/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/generation_classes_charm_choroid_lesions_gm.npy
prior_type = 'uniform'
prior_means =
prior_std =
# specific_stats = --specific_stats
# mix_prior_and_random = --mix_prior_and_random

## spatial deformation parameters ##
# no_flipping = --no_flipping
scaling =
rotation =
shearing =
translation = 
nonlin_std = 3
nonlin_shape_factor = (0.04, 0.25, 0.04)

## blurring/resampling parameters ##
# randomise_res = --randomise_res
data_res = (1, 4, 1)
thickness = (1, 0.01, 1)
downsample = --downsample
blur_range = 1.03

## bias field parameters ##
bias_std = .5
bias_shape_factor = (0.04, 0.25, 0.04)
# same_bias_for_all_channels = --same_bias_for_all_channels

## architecture parameters ##
n_levels = 5           # number of resolution levels
conv_per_level = 2  # number of convolution per level
conv_size = 3          # size of the convolution kernel (e.g. 3x3x3)
unet_feat = 24   # number of feature maps after the first convolution
activation = 'elu'     # activation for all convolution layers except the last, which will use sofmax regardless
feat_mult = 2    # if feat_multiplier is set to 1, we will keep the number of feature maps constant throughout the
#                        network; 2 will double them(resp. half) after each max-pooling (resp. upsampling);
#                        3 will triple them, etc.

## Training parameters ##
lr = 1e-4               # learning rate
lr_decay = 0            # learning rate decay (knowing that Adam already has its own internal decay)
wl2_epochs = 1          # number of pre-training epochs with wl2 metric w.r.t. the layer before the softmax
dice_epochs = 100       # number of training epochs
steps_per_epoch = 2500  # number of iteration per epoch
checkpoint = '' 		# checkpoint name

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: list
list:
	@LC_ALL=C $(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

remove-subject-copies:
	rm $(DATA_DIR)/SynthSeg_label_maps_manual_auto_photos_noCerebellumOrBrainstem/subject*copy*

create-subject-copies:
	python scripts/photos_utils.py

# training: PATH := $(PATH):/usr/pubsw/packages/CUDA/10.0/extras/CUPTI/lib64
training:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/10.1/lib64
	
	$(CMD) $(PROJ_DIR)/scripts/commands/training.py \
		$(labels_dir) \
		$(model_dir) \
		\
		--generation_labels $(generation_labels) \
		--segmentation_labels $(segmentation_labels) \
		--noisy_patches $(noisy_patches) \
		\
		--batch_size $(batch_size) \
		--channels $(channels) \
		--target_res $(target_res) \
		--output_shape $(output_shape) \
		\
		--generation_classes $(generation_classes) \
		--prior_type $(prior_type) \
		--prior_means $(prior_means) \
		--prior_std $(prior_std) \
		$(specific_stats) \
		$(mix_prior_and_random) \
		\
		$(no_flipping) \
		--scaling $(scaling) \
		--rotation $(rotation) \
		--shearing $(shearing) \
		--translation $(translation) \
		--nonlin_std '$(nonlin_std)' \
		--nonlin_shape_factor '$(nonlin_shape_factor)' \
		\
		$(randomise_res) \
		--data_res '$(data_res)' \
		--thickness '$(thickness)' \
		$(downsample) \
		--blur_range $(blur_range) \
		\
		--bias_std $(bias_std) \
		--bias_shape_factor '$(bias_shape_factor)' \
		$(same_bias_for_all_channels) \
		\
		--n_levels $(n_levels) \
		--conv_per_level $(conv_per_level) \
		--conv_size $(conv_size) \
		--unet_feat $(unet_feat) \
		--feat_mult $(feat_mult) \
		--activation $(activation) \
		\
		--lr $(lr) \
		--lr_decay $(lr_decay) \
		--wl2_epochs $(wl2_epochs) \
		--dice_epochs $(dice_epochs) \
		--steps_per_epoch $(steps_per_epoch) \
		--message 'changed learning rate, output shape and flipping is true, 3 channels, diff bias, E parameters' \
		;

predict:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/10.1/lib64

	$(CMD) $(PROJ_DIR)/scripts/commands/predict.py
	--model /cluster/scratch/friday/models/test_photos_no_brainstem_or_cerebellum/dice_038.h5 \
	--label_list /space/calico/1/users/Harsha/SynthSeg/data/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem//segmentation_new_charm_choroid_lesions.npy \
	--smoothing 0.5
	--biggest_component \
	--out_seg /tmp/seg4mm.mgz  /cluster/vive/UW_photo_recon/recons/results_Henry/Results_hard/17-0333/17-0333.hard.recon.grayscale.mgz