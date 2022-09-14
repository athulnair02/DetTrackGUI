%% TRACKING 3D
addpath('/nfs/scratch/athul/DetTrackGUI', '/nfs/scratch2/giuseppe/gd_repository')

slurm = parallel.importProfile('/nfs/scratch/athul/DetTrackGUI/SlurmProfile1.mlsettings');
parallel.defaultClusterProfile(slurm)

data=loadConditionData3D_m(%condDir%, ...
    {%chNames%}, {%markers%}) %creates array of paths

save('%data_filepath%', 'data')

clearvars -except data

% Calculating sigmas for detection
PSFrt = '%calibration_path%'; %copy file location from LLS calibrations of the same day as experiment
%psfs%

% a. How thick are the illumination planes? -> How big is the PSF?
%default_sigmas_calc%

% Sigmas obtained in pitch of 0.1, however plane distance  = 0.4 *
% sin(31.5), i.e. sigmaZ = sigmaZ488/(%zspace% * sin(31.5))

zRatio = (0.5 * sind(31.5))/0.1;

%default_sigmas%

GU_runDetTrack3d_m(data, 'Sigma', [%sigma_values%], 'Overwrite', [%overwrite_values%], 'TrackingRadius', [%tracking_radius_values%]);  % 1. deskew; 2. detection; 3. tracking; 4. track processing

%calc_img_proj_option%GU_calcImageProjections(data)

%bleach_option%bleach_in_a_box(data)

