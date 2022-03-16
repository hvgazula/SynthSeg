# Run all commands in one shell
.ONESHELL:

# Default target
.DEFAULT_GOAL := help

# Generic Variables
USR := $(shell whoami | head -c 2)
DT := $(shell date +"%Y%m%d")

# Fixed
HOME := /space/calico/1/users/Harsha
PROJ_DIR := $(shell pwd)
DATA_DIR := $(PROJ_DIR)/data
RESULTS_DIR := $(PROJ_DIR)/results
MODEL_DIR := $(PROJ_DIR)/models
SCRATCH_MODEL_DIR := /cluster/scratch/friday/for_harsha
ENV_DIR := $(HOME)/venvs

# Dynamic
ENV_NAME := synthseg-venv
# {synthseg-venv | synthseg-venv1}
CUDA_V := 10.1
PARAM_FILES_DIR = SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem
MODEL_NAME := VS05-noflip
CMD = sbatch --job-name=$(MODEL_NAME) submit.sh
# {echo | python | sbatch submit.sh}

ACTIVATE_ENV = source $(ENV_DIR)/$(ENV_NAME)/bin/activate
ACTIVATE_FS = source /usr/local/freesurfer/nmr-dev-env-bash

# variables for SynthSeg
labels_dir = $(DATA_DIR)/SynthSeg_label_maps_manual_auto_photos_noCerebellumOrBrainstem
MODEL_PATH = $(SCRATCH_MODEL_DIR)/$(MODEL_NAME)

## label maps parameters
generation_labels = $(DATA_DIR)/$(PARAM_FILES_DIR)/generation_charm_choroid_lesions.npy
segmentation_labels = $(DATA_DIR)/$(PARAM_FILES_DIR)/segmentation_new_charm_choroid_lesions.npy
noisy_patches = None

## output-related parameters
batch_size = 1
channels = 1
target_res =
output_shape = 160

# GMM-sampling parameters
generation_classes = $(DATA_DIR)/$(PARAM_FILES_DIR)/generation_classes_charm_choroid_lesions_gm.npy
prior_type = 'uniform'
prior_means =
prior_std =
# specific_stats = --specific_stats
# mix_prior_and_random = --mix_prior_and_random

## spatial deformation parameters ##
no_flipping = --no_flipping
scaling =
rotation =
shearing =
translation = 
nonlin_std = 3
nonlin_shape_factor = None

## blurring/resampling parameters ##
randomise_res = --randomise_res
data_res = None
thickness = (1, 1, 1)
downsample = --downsample
blur_range = 1.03

## bias field parameters ##
bias_std = .5
bias_shape_factor = None
# same_bias_for_all_channels = --same_bias_for_all_channels

## architecture parameters
n_levels = 5           	# number of resolution levels
conv_per_level = 2  	# number of convolution per level
conv_size = 3          	# size of the convolution kernel (e.g. 3x3x3)
unet_feat = 24   		# number of feature maps after the first convolution
activation = 'elu'     	# activation for all convolution layers except the last, which will use sofmax regardless
feat_mult = 2    		# if feat_multiplier is set to 1, we will keep the number of feature maps constant throughout the
# 							network; 2 will double them(resp. half) after each max-pooling (resp. upsampling);
#                       	3 will triple them, etc.

## Training parameters
lr = 1e-4               # learning rate
lr_decay = 0            # learning rate decay (knowing that Adam already has its own internal decay)
wl2_epochs = 1          # number of pre-training epochs with wl2 metric w.r.t. the layer before the softmax
dice_epochs = 100       # number of training epochs
steps_per_epoch = 2000  # number of iteration per epoch


.PHONY : help
help : Makefile
	@sed -n 's/^##//p' $<

.PHONY: list
list:
	@LC_ALL=C $(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

remove-subject-copies:
	rm $(DATA_DIR)/SynthSeg_label_maps_manual_auto_photos_noCerebellumOrBrainstem/subject*copy*

create-subject-copies:
	python scripts/photos_utils.py

## Running this target is equivalent to running tutorials/3-training.py
training-default:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/$(CUDA_V)/lib64

	python /autofs/space/calico_001/users/Harsha/SynthSeg/scripts/commands/training.py train\
			$(DATA_DIR)/training_label_maps \
			$(MODEL_DIR)/SynthSeg_training_BB_resume \
			\
			--generation_labels $(DATA_DIR)/labels_classes_priors/generation_labels.npy 		\
			--segmentation_labels $(DATA_DIR)/labels_classes_priors/segmentation_labels.npy 	\
			--batch_size 1 			\
			--channels 1 			\
			--target_res  			\
			--output_shape 96 		\
			--generation_classes $(DATA_DIR)/labels_classes_priors/generation_classes.npy 		\
			--prior_type 'uniform' 	\
			--scaling .15 			\
			--rotation 15 			\
			--shearing .012 		\
			--translation  			\
			--nonlin_std '3' 		\
			--randomise_res 		\
			--blur_range 1.03 		\
			--bias_std .5 			\
			--n_levels 5            \
			--conv_per_level 2   	\
			--conv_size 3           \
			--unet_feat 24    		\
			--feat_mult 2     		\
			--activation 'elu'      \
			--lr 1e-4               \
			--lr_decay 0            \
			--wl2_epochs 1          \
			--dice_epochs 10       	\
			--steps_per_epoch 75   	\
			;

# Use this target to train custom models
training:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	# export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/$(CUDA_V)/lib64
	
	$(CMD) $(PROJ_DIR)/scripts/commands/training.py train\
		$(labels_dir) \
		$(MODEL_PATH) \
		\
		--generation_labels $(generation_labels) \
		--segmentation_labels $(segmentation_labels) \
		--noisy_patches '$(noisy_patches)' \
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
		--wl2_epochs 1 \
		--dice_epochs $(dice_epochs) \
		--steps_per_epoch $(steps_per_epoch) \
		--message 'Flipping turned off' \
		;

## Use this target to resume training
resume-training:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/$(CUDA_V)/lib64
	
	python $(PROJ_DIR)/scripts/commands/training.py resume-train $(MODEL_PATH)


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

predict1:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/10.1/lib64

	$(CMD) $(PROJ_DIR)/scripts/commands/predict.py \
		--model /cluster/scratch/friday/for_harsha/20210819-436612/dice_076.h5 \
		--label_list /space/calico/1/users/Harsha/SynthSeg/data/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/segmentation_new_charm_choroid_lesions.npy \
		--out_seg /space/calico/1/users/Harsha/SynthSeg/results/UW_photos/segmentations-latest-192/ \
		--topology_classes /space/calico/1/users/Harsha/SynthSeg/data/SynthSeg_param_files_manual_auto_photos_noCerebellumOrBrainstem/topo_classes.npy \
		--smoothing 0.5 \
		--biggest_component \
		/space/calico/1/users/Harsha/SynthSeg/results/UW_photos/
		;

## predict-scans: Run MRI volumes through default SynthSeg
predict-scans:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/10.1/lib64

	python $(PROJ_DIR)/scripts/commands/SynthSeg_predict.py \
		--i $(RESULTS_DIR)/mri.scans/ \
		--o $(RESULTS_DIR)/mri.synthseg/ \
		--vol $(RESULTS_DIR)/volumes/mri.synthseg.volumes

## predict-soft: Run soft recons through custom SynthSeg model
predict-soft:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/10.1/lib64

	python scripts/commands/predict.py \
		--smoothing 0.5 \
		--biggest_component \
		--padding 256 \
		--vol $(RESULTS_DIR)/volumes/soft.synthseg.volumes \
		$(RESULTS_DIR)/soft.recon/ \
		$(RESULTS_DIR)/soft.synthseg/ \
		$(PROJ_DIR)/models/jei-model/SynthSegPhotos_no_brainstem_or_cerebellum_4mm.h5 \
		$(PROJ_DIR)/models/jei-model/SynthSegPhotos_no_brainstem_or_cerebellum_4mm.label_list.npy

## predict-soft: Run hard recons through custom SynthSeg model
predict-hard:
	$(ACTIVATE_ENV)
	export PYTHONPATH=$(PROJ_DIR)
	export LD_LIBRARY_PATH=$(LD_LIBRARY_PATH):/usr/pubsw/packages/CUDA/10.1/lib64

	python scripts/commands/predict.py \
		--smoothing 0.5 \
		--biggest_component \
		--padding 256 \
		--vol $(RESULTS_DIR)/volumes/hard.synthseg.volumes \
		$(RESULTS_DIR)/hard.recon/ \
		$(RESULTS_DIR)/hard.synthseg/ \
		$(PROJ_DIR)/models/jei-model/SynthSegPhotos_no_brainstem_or_cerebellum_4mm.h5 \
		$(PROJ_DIR)/models/jei-model/SynthSegPhotos_no_brainstem_or_cerebellum_4mm.label_list.npy


samseg-%: SUB_ID = 17-0333 18-0086 18-0444 18-0817 18-1045 18-1132 18-1196 18-1274 18-1327 18-1343 18-1470 18-1680 18-1690 18-1704 18-1705 18-1724 18-1754 18-1913 18-1930 18-2056 18-2128 18-2259 18-2260 19-0019 19-0037 19-0100 19-0138 19-0148
samseg-%: FSDEV = /space/calico/1/users/Harsha/photo-samseg
samseg-hard-new-recons:
	$(ACTIVATE_FS)
	export PYTHONPATH=$(FSDEV)/python/packages
	
	for sub_id in $(SUB_ID); do \
		sbatch submit-samseg.sh $(FSDEV)/python/scripts/run_samseg \
		-i /cluster/vive/UW_photo_recon/Photo_data/$$sub_id/ref_mask/photo_recon.mgz \
		-o $(RESULTS_DIR)/SAMSEG_OUTPUT_HARD_C2/$$sub_id \
		--threads 64 \
		--dissection-photo both \
		--atlas $(FSDEV)/atlas; \
	done

samseg-soft-new-recons:
	$(ACTIVATE_FS)
	export PYTHONPATH=$(FSDEV)/python/packages
	
	for sub_id in $(SUB_ID); do \
		sbatch submit-samseg.sh $(FSDEV)/python/scripts/run_samseg \
			-i /cluster/vive/UW_photo_recon/Photo_data/$$sub_id/ref_soft_mask/photo_recon.mgz \
			-o $(RESULTS_DIR)/SAMSEG_OUTPUT_SOFT_C2/$$sub_id \
			--threads 64 \
			--dissection-photo both \
			--atlas $(FSDEV)/atlas; \
	done

## samseg-hard-on-old-recons: Run FS SAMSEG on old hard reconstructions
# stupid mri_convert does not create directories for us and thus
# the use of mkdir (:grimace:)
samseg-hard-on-old-recons:
	$(ACTIVATE_FS)
	export PYTHONPATH=$(FSDEV)/python/packages
	
	for sub_id in $(SUB_ID); do \
		mkdir -p $(RESULTS_DIR)/SAMSEG_OUTPUT_HARD_C2/$$sub_id
		mri_convert /cluster/vive/UW_photo_recon/recons/results_Henry/Results_hard/$$sub_id/$$sub_id".hard.recon.mgz" $(RESULTS_DIR)/SAMSEG_OUTPUT_HARD_C2/$$sub_id/input.mgz
		sbatch submit-samseg.sh $(FSDEV)/python/scripts/run_samseg \
		-i $(RESULTS_DIR)/SAMSEG_OUTPUT_HARD_C2/$$sub_id/input.mgz \
		-o $(RESULTS_DIR)/SAMSEG_OUTPUT_HARD_C2/$$sub_id \
		--threads 64 \
		--dissection-photo both \
		--atlas $(FSDEV)/atlas; \
	done

## samseg-soft-on-old-recons: Run FS SAMSEG on old soft reconstructions
samseg-soft-on-old-recons:
	$(ACTIVATE_FS)
	export PYTHONPATH=$(FSDEV)/python/packages
	
	for sub_id in $(SUB_ID); do \
		sbatch submit-samseg.sh $(FSDEV)/python/scripts/run_samseg \
			-i /cluster/vive/UW_photo_recon/recons/results_Henry/Results_soft/$$sub_id/soft/$$sub_id"_soft.mgz" \
			-o $(RESULTS_DIR)/SAMSEG_OUTPUT_SOFT_C2/$$sub_id \
			--threads 64 \
			--dissection-photo both \
			--atlas $(FSDEV)/atlas; \
	done

