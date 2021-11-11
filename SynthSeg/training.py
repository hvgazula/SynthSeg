# python imports
import os
from inspect import getmembers, isclass

import keras
import keras.callbacks as KC
import numpy as np
import tensorflow as tf
# third-party imports
from ext.lab2im import layers as l2i_layers
from ext.lab2im import utils
from ext.neuron import layers as nrn_layers
from ext.neuron import models as nrn_models
from keras import models
from keras.optimizers import Adam

# project imports
from . import metrics_model as metrics
from .brain_generator import BrainGenerator

physical_devices = tf.config.list_physical_devices('GPU')
print("Num GPUs:", len(physical_devices))

def training(labels_dir,
             model_dir,
             generation_labels=None,
             segmentation_labels=None,
             patch_dir=None,
             batchsize=1,
             n_channels=1,
             target_res=None,
             output_shape=None,
             generation_classes=None,
             prior_distributions='uniform',
             prior_means=None,
             prior_stds=None,
             use_specific_stats_for_channel=False,
             mix_prior_and_random=False,
             flipping=True,
             scaling_bounds=.15,
             rotation_bounds=15,
             shearing_bounds=.012,
             translation_bounds=False,
             nonlin_std=3.,
             nonlin_shape_factor=.04,
             randomise_res=True,
             max_res_iso=4.,
             max_res_aniso=8.,
             data_res=None,
             thickness=None,
             downsample=False,
             blur_range=1.03,
             bias_field_std=.5,
             bias_shape_factor=.025,
             same_bias_for_all_channels=False,
             n_levels=5,
             nb_conv_per_level=2,
             conv_size=3,
             unet_feat_count=24,
             feat_multiplier=2,
             activation='elu',
             lr=1e-4,
             lr_decay=0,
             wl2_epochs=5,
             dice_epochs=200,
             steps_per_epoch=1000,
             checkpoint=None):
    """
    This function trains a Unet to segment MRI images with synthetic scans generated by sampling a GMM conditioned on
    label maps. We regroup the parameters in three categories: Generation, Architecture, Training.

    # IMPORTANT !!!
    # Each time we provide a parameter with separate values for each axis (e.g. with a numpy array or a sequence),
    # these values refer to the RAS axes.

    :param labels_dir: path of folder with all input label maps, or to a single label map (if only one training example)
    :param model_dir: path of a directory where the models will be saved during training.

    #---------------------------------------------- Generation parameters ----------------------------------------------
    # label maps parameters
    :param generation_labels: (optional) list of all possible label values in the input label maps.
    Default is None, where the label values are directly gotten from the provided label maps. If not None, must be a
    list, or a 1d numpy array, or the path to such an array, which should be organised as follows: background label
    first, then non-sided labels (e.g. CSF, brainstem, etc.), then all the structures of the same hemisphere (can be
    left or right), and finally all the corresponding contralateral structures (in the same order).
    :param segmentation_labels: (optional) list of the same length as generation_labels to indicate which values to use
    in the training label maps, i.e. all occurences of generation_labels[i] in the input label maps will be converted to
    output_labels[i] in the returned label maps. Examples:
    Set output_labels[i] to zero if you wish to erase the value generation_labels[i] from the returned label maps.
    Set output_labels[i]=generation_labels[i] if you wish to keep the value generation_labels[i] in the returned maps.
    Can be a list or a 1d numpy array, or the path to such an array. Default is output_labels = generation_labels.

    # output-related parameters
    :param batchsize: (optional) number of images to generate per mini-batch. Default is 1.
    :param n_channels: (optional) number of channels to be synthetised. Default is 1.
    :param target_res: (optional) target resolution of the generated images and corresponding label maps.
    If None, the outputs will have the same resolution as the input label maps.
    Can be a number (isotropic resolution), or the path to a 1d numpy array.
    :param output_shape: (optional) desired shape of the output image, obtained by randomly cropping the generated image
    Can be an integer (same size in all dimensions), a sequence, a 1d numpy array, or the path to a 1d numpy array.
    Default is None, where no cropping is performed.

    # GMM-sampling parameters
    :param generation_classes: (optional) Indices regrouping generation labels into classes of same intensity
    distribution. Regouped labels will thus share the same Gaussian when samling a new image. Should be the path to a 1d
    numpy array with the same length as generation_labels. and contain values between 0 and K-1, where K is the total
    number of classes. Default is all labels have different classes.
    Can be a list or a 1d numpy array, or the path to such an array.
    :param prior_distributions: (optional) type of distribution from which we sample the GMM parameters.
    Can either be 'uniform', or 'normal'. Default is 'uniform'.
    :param prior_means: (optional) hyperparameters controlling the prior distributions of the GMM means. Because
    these prior distributions are uniform or normal, they require by 2 hyperparameters. Can be a path to:
    1) an array of shape (2, K), where K is the number of classes (K=len(generation_labels) if generation_classes is
    not given). The mean of the Gaussian distribution associated to class k in [0, ...K-1] is sampled at each mini-batch
    from U(prior_means[0,k], prior_means[1,k]) if prior_distributions is uniform, and from
    N(prior_means[0,k], prior_means[1,k]) if prior_distributions is normal.
    2) an array of shape (2*n_mod, K), where each block of two rows is associated to hyperparameters derived
    from different modalities. In this case, if use_specific_stats_for_channel is False, we first randomly select a
    modality from the n_mod possibilities, and we sample the GMM means like in 2).
    If use_specific_stats_for_channel is True, each block of two rows correspond to a different channel
    (n_mod=n_channels), thus we select the corresponding block to each channel rather than randomly drawing it.
    Default is None, which corresponds all GMM means sampled from uniform distribution U(25, 225).
    :param prior_stds: (optional) same as prior_means but for the standard deviations of the GMM.
    Default is None, which corresponds to U(5, 25).
    :param use_specific_stats_for_channel: (optional) whether the i-th block of two rows in the prior arrays must be
    only used to generate the i-th channel. If True, n_mod should be equal to n_channels. Default is False.
    :param mix_prior_and_random: (optional) if prior_means is not None, enables to reset the priors to their default
    values for half of thes cases, and thus generate images of random contrast.

    # spatial deformation parameters
    :param flipping: (optional) whether to introduce right/left random flipping. Default is True.
    :param scaling_bounds: (optional) if apply_linear_trans is True, the scaling factor for each dimension is
    sampled from a uniform distribution of predefined bounds. Can either be:
    1) a number, in which case the scaling factor is independently sampled from the uniform distribution of bounds
    (1-scaling_bounds, 1+scaling_bounds) for each dimension.
    2) the path to a numpy array of shape (2, n_dims), in which case the scaling factor in dimension i is sampled from
    the uniform distribution of bounds (scaling_bounds[0, i], scaling_bounds[1, i]) for the i-th dimension.
    3) False, in which case scaling is completely turned off.
    Default is scaling_bounds = 0.15 (case 1)
    :param rotation_bounds: (optional) same as scaling bounds but for the rotation angle, except that for case 1 the
    bounds are centred on 0 rather than 1, i.e. (0+rotation_bounds[i], 0-rotation_bounds[i]).
    Default is rotation_bounds = 15.
    :param shearing_bounds: (optional) same as scaling bounds. Default is shearing_bounds = 0.012.
    :param translation_bounds: (optional) same as scaling bounds. Default is translation_bounds = False, but we
    encourage using it when cropping is deactivated (i.e. when output_shape=None).
    :param nonlin_std: (optional) Standard deviation of the normal distribution from which we sample the first
    tensor for synthesising the deformation field. Set to 0 to completely deactivate elastic deformation.
    :param nonlin_shape_factor: (optional) Ratio between the size of the input label maps and the size of the sampled
    tensor for synthesising the elastic deformation field.

    # blurring/resampling parameters
    :param randomise_res: (optional) whether to mimic images that would have been 1) acquired at low resolution, and
    2) resampled to high esolution. The low resolution is uniformly resampled at each minibatch from [1mm, 9mm].
    In that process, the images generated by sampling the GMM are: 1) blurred at the sampled LR, 2) downsampled at LR,
    and 3) resampled at target_resolution.
    :param max_res_iso: (optional) If randomise_res is True, this enables to control the upper bound of the uniform
    distribution from which we sample the random resolution U(min_res, max_res_iso), where min_res is the resolution of
    the input label maps. Must be a number, and default is 4. Set to None to deactivate it, but if randomise_res is
    True, at least one of max_res_iso or max_res_aniso must be given.
    :param max_res_aniso: If randomise_res is True, we this enables to downsample the input volumes to a random LR in
    only 1 (random) direction. This is done by randomly selecting a direction i in the range [0, n_dims-1], and sampling
    a value in the corresponding uniform distribution U(min_res[i], max_res_aniso[i]), where min_res is the resolution
    of the input label maps. Can be a number, a sequence, or a 1d numpy array. Set to None to deactivate it, but if
    randomise_res is True, at least one of max_res_iso or max_res_aniso must be given.
    :param data_res: (optional) specific acquisition resolution to mimic, as opposed to random resolution sampled when
    randomis_res is True. This triggers a blurring which mimics the acquisition resolution, but downsampling is optional
    (see param downsample). Default for data_res is None, where images are slighlty blurred. If the generated images are
    uni-modal, data_res can be a number (isotropic acquisition resolution), a sequence, a 1d numpy array, or the path
    to a 1d numy array. In the multi-modal case, it should be given as a umpy array (or a path) of size (n_mod, n_dims),
    where each row is the acquisition resolution of the corresponding channel.
    :param thickness: (optional) if data_res is provided, we can further specify the slice thickness of the low
    resolution images to mimic. Must be provided in the same format as data_res. Default thickness = data_res.
    :param downsample: (optional) whether to actually downsample the volume images to data_res after blurring.
    Default is False, except when thickness is provided, and thickness < data_res.
    :param blur_range: (optional) Randomise the standard deviation of the blurring kernels, (whether data_res is given
    or not). At each mini_batch, the standard deviation of the blurring kernels are multiplied by a coefficient sampled
    from a uniform distribution with bounds [1/blur_range, blur_range]. If None, no randomisation. Default is 1.15.

    # bias field parameters
    :param bias_field_std: (optional) If strictly positive, this triggers the corruption of images with a bias field.
    The bias field is obtained by sampling a first small tensor from a normal distribution, resizing it to
    full size, and rescaling it to positive values by taking the voxel-wise exponential. bias_field_std designates the
    std dev of the normal distribution from which we sample the first tensor.
    Set to 0 to completely deactivate biad field corruption.
    :param bias_shape_factor: (optional) If bias_field_std is not False, this designates the ratio between the size of
    the input label maps and the size of the first sampled tensor for synthesising the bias field.
    :param same_bias_for_all_channels: (optional) If same_bias_for_all_channels is not False, this applies the same bias
    in all channels.

    # ------------------------------------------ UNet architecture parameters ------------------------------------------
    :param n_levels: (optional) number of level for the Unet. Default is 5.
    :param nb_conv_per_level: (optional) number of convolutional layers per level. Default is 2.
    :param conv_size: (optional) size of the convolution kernels. Default is 2.
    :param unet_feat_count: (optional) number of feature for the first layr of the Unet. Default is 24.
    :param feat_multiplier: (optional) multiply the number of feature by this nummber at each new level. Default is 2.
    :param activation: (optional) activation function. Can be 'elu', 'relu'.

    # ----------------------------------------------- Training parameters ----------------------------------------------
    :param lr: (optional) learning rate for the training. Default is 1e-4
    :param lr_decay: (optional) learing rate decay. Default is 0, where no decay is applied.
    :param wl2_epochs: (optional) number of epohs for which the network (except the soft-max layer) is trained with L2
    norm loss function. Default is 5.
    :param dice_epochs: (optional) number of epochs with the soft Dice loss function. default is 200.
    :param steps_per_epoch: (optional) number of steps per epoch. Default is 1000. Since no online validation is
    possible, this is equivalent to the frequency at which the models are saved.
    :param checkpoint: (optional) path of an already saved model to load before starting the training.
    """

    # check epochs
    assert (wl2_epochs > 0) | (dice_epochs > 0), \
        'either wl2_epochs or dice_epochs must be positive, had {0} and {1}'.format(wl2_epochs, dice_epochs)

    # get label lists
    generation_labels, n_neutral_labels = utils.get_list_labels(label_list=generation_labels,
                                                                labels_dir=labels_dir,
                                                                FS_sort=False)
    if segmentation_labels is not None:
        segmentation_labels, _ = utils.get_list_labels(
            label_list=segmentation_labels)
    else:
        segmentation_labels = generation_labels
    n_segmentation_labels = len(np.unique(segmentation_labels))

    # instantiate BrainGenerator object
    brain_generator = BrainGenerator(labels_dir=labels_dir,
                                     generation_labels=generation_labels,
                                     output_labels=segmentation_labels,
                                     patch_dir=patch_dir,
                                     n_neutral_labels=n_neutral_labels,
                                     batchsize=batchsize,
                                     n_channels=n_channels,
                                     target_res=target_res,
                                     output_shape=output_shape,
                                     output_div_by_n=2 ** n_levels,
                                     generation_classes=generation_classes,
                                     prior_distributions=prior_distributions,
                                     prior_means=prior_means,
                                     prior_stds=prior_stds,
                                     use_specific_stats_for_channel=use_specific_stats_for_channel,
                                     mix_prior_and_random=mix_prior_and_random,
                                     flipping=flipping,
                                     scaling_bounds=scaling_bounds,
                                     rotation_bounds=rotation_bounds,
                                     shearing_bounds=shearing_bounds,
                                     translation_bounds=translation_bounds,
                                     nonlin_std=nonlin_std,
                                     nonlin_shape_factor=nonlin_shape_factor,
                                     randomise_res=randomise_res,
                                     max_res_iso=max_res_iso,
                                     max_res_aniso=max_res_aniso,
                                     data_res=data_res,
                                     thickness=thickness,
                                     downsample=downsample,
                                     blur_range=blur_range,
                                     bias_field_std=bias_field_std,
                                     bias_shape_factor=bias_shape_factor,
                                     same_bias_for_all_channels=same_bias_for_all_channels)

    # generation model
    labels_to_image_model = brain_generator.labels_to_image_model
    unet_input_shape = brain_generator.model_output_shape

    # prepare the segmentation model
    unet_model = nrn_models.unet(nb_features=unet_feat_count,
                                 input_shape=unet_input_shape,
                                 nb_levels=n_levels,
                                 conv_size=conv_size,
                                 nb_labels=n_segmentation_labels,
                                 feat_mult=feat_multiplier,
                                 nb_conv_per_level=nb_conv_per_level,
                                 batch_norm=-1,
                                 activation=activation,
                                 input_model=labels_to_image_model)

    # input generator
    input_generator = utils.build_training_generator(
        brain_generator.model_inputs_generator, batchsize)

    # pre-training with weighted L2, input is fit to the softmax rather than the probabilities
    if wl2_epochs > 0:
        wl2_model = models.Model(
            unet_model.inputs,
            [unet_model.get_layer('unet_likelihood').output])
        wl2_model = metrics.metrics_model(wl2_model, segmentation_labels,
                                          'wl2')
        train_model(wl2_model, input_generator, lr, lr_decay, wl2_epochs,
                    steps_per_epoch, model_dir, 'wl2', checkpoint)
        checkpoint = os.path.join(model_dir, 'wl2_%03d.h5' % wl2_epochs)

    # fine-tuning with dice metric
    dice_model = metrics.metrics_model(unet_model, segmentation_labels, 'dice')
    train_model(dice_model, input_generator, lr, lr_decay, dice_epochs,
                steps_per_epoch, model_dir, 'dice', checkpoint)


def train_model(model,
                generator,
                learning_rate,
                lr_decay,
                n_epochs,
                n_steps,
                model_dir,
                metric_type,
                path_checkpoint=None,
                reinitialise_momentum=False):

    # prepare model and log folders
    utils.mkdir(model_dir)
    log_dir = os.path.join(model_dir, 'logs')
    utils.mkdir(log_dir)

    # model saving callback
    save_file_name = os.path.join(model_dir, '%s_{epoch:03d}.h5' % metric_type)
    callbacks = [KC.ModelCheckpoint(save_file_name, verbose=1)]

    # TensorBoard callback
    if metric_type == 'dice':
        callbacks.append(
            KC.TensorBoard(log_dir=log_dir,
                           histogram_freq=0,
                           write_graph=True,
                           write_images=False))

    compile_model = True
    init_epoch = 0
    if path_checkpoint is not None:
        if metric_type in path_checkpoint:
            init_epoch = int(
                os.path.basename(path_checkpoint).split(metric_type)[1][1:-3])
        if (not reinitialise_momentum) & (metric_type in path_checkpoint):
            custom_l2i = {
                key: value
                for (key, value) in getmembers(l2i_layers, isclass)
                if key != 'Layer'
            }
            custom_nrn = {
                key: value
                for (key, value) in getmembers(nrn_layers, isclass)
                if key != 'Layer'
            }
            custom_objects = {
                **custom_l2i,
                **custom_nrn, 'tf': tf,
                'keras': keras,
                'loss': metrics.IdentityLoss().loss
            }
            model = models.load_model(path_checkpoint,
                                      custom_objects=custom_objects)
            compile_model = False
        else:
            model.load_weights(path_checkpoint, by_name=True)
        # else:
        # path_checkpoint = '/space/calico/1/users/Harsha/SynthSeg/models/SynthSeg.h5'
        # try:
        #     model.load_weights(path_checkpoint, by_name=True)
        # except:
        #     for l in model.layers:
        #         if l.name=='unet_likelihood':
        #             l.name='unet_likelihood_'
        #     model.load_weights(path_checkpoint, by_name=True)
        # for l in model.layers:
        #     if l.name=='unet_likelihood_':
        #         l.name='unet_likelihood'

    # compile
    if compile_model:
        model.compile(optimizer=Adam(lr=learning_rate, decay=lr_decay),
                      loss=metrics.IdentityLoss().loss,
                      loss_weights=[1.0])

    # fit
    model.fit_generator(generator,
                        epochs=n_epochs,
                        steps_per_epoch=n_steps,
                        callbacks=callbacks,
                        initial_epoch=init_epoch)
