# Detection and Tracking Graphical User Interface

![Screenshot 2023-05-15 at 9 06 20 AM](https://github.com/athulnair02/DetTrackGUI/assets/42418601/7b9225b6-8f7c-4c6e-9aae-2b0353f043bc)

## Running the GUI

In your terminal, run the command 
```bash
/nfs/scratch/athul/DetTrackGUI/DT_GUI
```
Another option is to download the executable directly off github with the command
```bash
curl -sL 'https://raw.githubusercontent.com/athulnair02/DetTrackGUI/main/DT_GUI' > DT_GUI && chmod +x ./DT_GUI
```
and run that executable.

> It is advised to run the executable from the terminal instead of double-clicking the executable from the graphical file explorer so logging messages and errors can be seen to ensure everything is running correctly.

## Requirements
### File Structure Example
> Note: The deeper levels of the tree are not shown like the .tiff images inside the channel folders of the individual experiments or the files inside subfolders of LLSCalibrations
```
.
├─── CS1
│    ├─── Ex01_488_300mW_560_500mW_642_500mW_z0p5
│    │    ├─── ch488CamA
│    │    ├─── ch560CamB
│    │    └─── ch642CamA
│    └─── Ex02_488_300mW_560_500mW_642_500mW_z0p5
│         ├─── ch488CamA
│         ├─── ch560CamB
│         └─── ch642CamA
└─── LLSCalibrations
     ├─── blk
     ├─── chroma
     ├─── illum
     ├─── sampleplane
     ├─── XZPSF
     ├─── 488totalPSF.tiff
     ├─── 560totalPSF.tiff
     └─── 642totalPSF.tiff 
```


### Directory naming schemes
- Calibration Folder: `LLSCalibrations`
- Experiment Folders: must start with `Ex` and end with the zsapce looking like `_z0p5`
- Cover Slip Folders: must start with `CS`
- Channels in Claibration Folders: `.tiff` files must look like `488totalPSF.tiff` starting with the channel value
- Channels in Experiment Folders: must look like `ch488nmCamA` including the channel value


## Using the GUI
1. Select if you want to run detection on an entire coverslip or a single experiemnt
2. Browse the appropriate folder for detection (make sure to open the folder to select it)
3. Select the primary channel and secondary channels you need and enter a corresponding marker
4. Enter a tracking radius lower and upper bounds if you do not want to use the default values
5. Select if you want to overwrite any processes
6. If you want custom sigma values for the channels you chose, select the corresponding channel number and enter the XY and Z values you wish to use.
7. If you want to run `GU_calcImageProjections` or `bleach_in_a_box` after detection and tracking, you can select your choices
8. Enter a valid email to send results to if the detection worked as expected or if there were any errors on the way.
9. Finally, click "Run" to allow the program run on the inputs you entered.

## Output
If no error was present, the output files from running the program can be found in a specifc location. In each experiement folder (regardless of running on an experiment or cover slip), the primary channel will have a new subfolder inside it, `Analysis`.

```
Ex01_488_300mW_560_500mW_642_500mW_z0p5
├─── ch488CamA
├─── ch560CamB
└─── ch642CamA
     ├─── Analysis
     │    ├─── backup_08_23_2022_00_17
     │    │    ├─── data_642.mat
     │    │    ├─── Detection3D.mat
     │    │    ├─── DetectionNTracking_result.m
     │    │    ├─── ProcessedTracks.mat
     │    │    ├─── RotatedTracks.mat
     │    │    └─── trackedFeatures.mat
     │    ├─── backup_09_15_2022_13_31
     │    │    ├─── data_642_488.mat
     │    │    ├─── Detection3D.mat
     │    │    ├─── DetectionNTracking_result.m
     │    │    ├─── ProcessedTracks.mat
     │    │    ├─── RotatedTracks.mat
     │    │    └─── trackedFeatures.mat
     │    ├─── Detection3D.mat
     │    ├─── ProcessedTracks.mat
     │    ├─── RotatedTracks.mat
     │    └─── trackedFeatures.mat
     ├─── DS
     ├─── Ex02_CamA_ch2.....tiff
     └─── Ex02_CamA_ch2.....tiff
```

Above is an example of a experiment folder after the program was run on it. In this case, the 642nm channel was the primary channel since that is where the Analysis folder has been generated. Within this folder, there are 4 `.mat` files and backup folders. The `.mat` files are the most recent output of the program and what is typically used for the next steps of the research process.

The backup folders, however, were a feature added to keep track of what settings were used to run detection and tracking at a specific moment of time. In this case, the experiment was ran twice with channel 648nm as the primary channel. Once at 8/23/2023 00:17 and another at 9/15/2023 13:31. The files produced from the latter date is found both inside the backup folder and in the Analysis folder (duplicates). In the backup folder, there are 2 additional files saved. `data_642_488.mat` is the data stored for when the program was ran with channel 642nm as the primary and with one secondary channel 488nm as dictated by the filename. `DetectionNTracking_result.m` is the matlab file that was altered from a template to produce these results and can be viewed to ensure correct inputs and possibly alter for a even more customized result.

## Future Improvements
Any future improvements or suggestions can be redirected to @athulnair02 (athulnair@utexas.edu).

## Future Improvements
Any future improvements or suggestions can be redirected to @athulnair02 (athulnair@utexas.edu).