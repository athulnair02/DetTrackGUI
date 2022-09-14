function GU_runDetTrack3d(varargin)

ip = inputParser;
ip.CaseSensitive = false;
ip.KeepUnmatched = true;
ip.addOptional('data', [], @isstruct); % data structure from loadConditionData
ip.addOptional('apath', []); % analysis path
ip.addParamValue('Overwrite', false, @islogical); % 1. deskew; 2. detection; 3. tracking; 4. track processing

% detection options
ip.addParamValue('SkewAngle', 31.5, @isscalar);
ip.addParamValue('Sigma', [1.26, 1.32; 1.41, 1.38;  1.58, 1.608;]); % for 0.5sample scan [1.41, 1.38; 1.26, 1.308; 1.58, 1.608;] %for z 0.6 [1.58, 1.34;1.41, 1.15; 1.26, 1.09;] based on zAniso = 2.5 sampling; hex [1.23, 1.88; 1.42, 2.2] // sq:[1.23, 2.54; 1.42, 3.15;]
ip.addParamValue('WindowSize', []);
ip.addParamValue('Mode', 'xyzAc', @ischar); % do not change unless necessary
ip.addParamValue('FitMixtures', false, @islogical); % fairly robust
ip.addParamValue('MaxMixtures', 3, @(x) numel(x)==1 && x>0 && round(x)==x);

% tracking options
ip.addParamValue('Track', true, @islogical);
ip.addParamValue('RotateTracks', true, @islogical);
ip.addParamValue('TrackingRadius', [3 6], @(x) numel(x)==2);
ip.addParamValue('TrackingGapLength', 2, @(x) numel(x)==1);
ip.addParamValue('Buffer', [3 3]);
ip.addParamValue('BufferAll', false, @islogical);

% deskew options
ip.addParamValue('sCMOSCameraFlip', false, @islogical); % necessary when frame rotation is off during SLICE acq.
ip.addParamValue('Crop', false, @islogical);
ip.addParamValue('Rotate', false, @islogical);

% light sheet flat field corrections options below
ip.addParamValue('LLFFCorrection', false, @islogical);
ip.addParamValue('LowerLimit', 0.4, @isnumeric); % this value is the lowest
ip.addParamValue('LSImageCh1', '' , @isstr);
ip.addParamValue('LSImageCh2', '' , @isstr);
ip.addParamValue('LSImageCh3', '' , @isstr);
ip.addParamValue('LSImageCh4', '' , @isstr);
ip.addParamValue('BackgroundCh1', '' , @isstr);
ip.addParamValue('BackgroundCh2', '' , @isstr);
ip.addParamValue('BackgroundCh3', '' , @isstr);
ip.addParamValue('BackgroundCh4', '' , @isstr);

ip.parse(varargin{:});
data = ip.Results.data;
apath = ip.Results.apath;
pr = ip.Results;
overwrite = ip.Results.Overwrite;
if numel(overwrite)==1
    overwrite = repmat(overwrite, [1 4]);
end

sigma = ip.Results.Sigma;
if isempty(sigma)
    fprintf('Enter the Gaussian s.d. for detection. If the z-value is different, \n');
    sigma = input('enter the two values as, e.g., "[1.5 1.3]": ');
end

LLCopts = {'LLFFCorrection',pr.LLFFCorrection, 'LowerLimit', pr.LowerLimit, 'LSImageCh1', pr.LSImageCh1, 'LSImageCh2',pr.LSImageCh2, 'LSImageCh3',pr.LSImageCh3,'LSImageCh4',pr.LSImageCh4,...
    'BackgroundCh1',pr.BackgroundCh1,'BackgroundCh2',pr.BackgroundCh2,'BackgroundCh3',pr.BackgroundCh3,'BackgroundCh4',pr.BackgroundCh4};
% settings -> input options instead (check all, vs single)
% improve help for this function

%-------------------------------------------------------------------------------
% 1) Parse data, determine output structure
%-------------------------------------------------------------------------------
class(apath)
if isempty(data)
    data = loadConditionData3D();
end

if isempty(apath) % store results locally in cell/Analysis directory
    apath = arrayfun(@(i) [i.source 'Analysis' filesep], data, 'unif', 0);
else
    % expand results path for all data sets
    %apath = arrayfun(@(i) [apath getShortPath(i,3) filesep 'Analysis' filesep], data, 'unif', 0);
    apath = arrayfun(@(i) [apath], data, 'unif', 0);
end

[~,~] = cellfun(@mkdir, apath, 'unif', 0);
% 

data = deskewData(data, 'Overwrite', overwrite(1), 'SkewAngle', ip.Results.SkewAngle,...
    'Rotate', ip.Results.Rotate,'sCMOSCameraFlip',ip.Results.sCMOSCameraFlip, 'Crop', ip.Results.Crop, LLCopts{:});

%-------------------------------------------------------------------------------
% 3) Detection
%-------------------------------------------------------------------------------
tic
GU_runDetection3D(data, 'Sigma', sigma, 'Overwrite', overwrite(2),...
    'WindowSize', ip.Results.WindowSize, 'ResultsPath', apath,'Mode', ip.Results.Mode,...
    'FitMixtures',pr.FitMixtures, 'MaxMixtures',pr.MaxMixtures);
toc
%-------------------------------------------------------------------------------
% 4) Tracking
%-------------------------------------------------------------------------------
if ip.Results.Track
    data = data(~([data.movieLength]==1));
    runTracking3D(data, loadTrackSettings('Radius', ip.Results.TrackingRadius,...
        'MaxGapLength', ip.Results.TrackingGapLength),...
        'FileName', 'trackedFeatures.mat', 'Overwrite', overwrite(3), 'ResultsPath', apath);
    
    GU_runTrackProcessing3D(data, 'Overwrite', overwrite(4),...
        'TrackerOutput', 'trackedFeatures.mat', 'FileName', 'ProcessedTracks.mat',...
        'Buffer', ip.Results.Buffer, 'BufferAll', ip.Results.BufferAll,...
        'FitMixtures',pr.FitMixtures, 'WindowSize', ip.Results.WindowSize, 'ResultsPath', apath);
    
    %-------------------------------------------------------------------------------
    % 5) Rotate tracks
    %-------------------------------------------------------------------------------
    if ip.Results.RotateTracks
        rotateTracks3D(data, 'Overwrite', overwrite(4), 'Crop', ip.Results.Crop);
    end
end