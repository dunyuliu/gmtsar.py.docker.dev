#! /usr/bin/env python3
import os, time
import numpy as np
import xarray as xr
from skimage import io
from skimage.metrics import structural_similarity as ssim
import matplotlib.pyplot as plt
from pathListForTest import caseNameList, intfDirList, rawDir, SLCDir

fileNameList = ['corr_ll.png','display_amp_ll.png','phasefilt_mask_ll.png',
        'corr_ll.grd', 'phasefilt.grd', 'filtcorr.grd']
refRoot  = 'csh.test'
testRoot = 'py.test'
fileDiffNumericThreshold = 1e-3
imageSimilarityIndexThreshold = 0.999

def parseCmdOutput(fn, searchStr):
    with open(fn,'r') as f:
        for line in f:
            if searchStr in line:
                val = line.split()
                keyIndex = val.index(searchStr)
                result = float(val[keyIndex+1])
    return result

def compare_nc_files(fn1,fn2,threshold=1e-3):
    isTheSame = 'SUCCESS '+fn1+' '+fn2
    f1 = xr.open_dataset(fn1)
    f2 = xr.open_dataset(fn2)
    metadata_equal = f1.identical(f2)
    data_equal = (f1==f2).all().items()

    # Compare variables
    for var in f1.variables:
        var1 = f1[var]
        var2 = f2[var]
        assert var1.dims == var2.dims, 'FAIL var dim '+fn1+' '+fn2
    assert metadata_equal, 'FAIL metadata '+fn1+' '+fn2
    xr.testing.assert_allclose(f1,f2)
    return isTheSame

def compare_txt_files(fn1,fn2,threshold=1e-3):
    isTheSame = 'SUCCESS '+fn1+' '+fn2
    with open(fn1,'r') as f1, open(fn2,'r') as f2:
        result1 = f1.read().split()
        result2 = f2.read().split()
    assert len(result1) == len(result2), 'FAIL '+fn1+' '+fn2
    for num1,num2 in zip(result1,result2):
        fnum1, fnum2 = float(num1),float(num2)
        assert abs(fnum1-fnum2) < threshold, 'FAIL '+fn1+' '+fn2
    print(isTheSame)

def compare_files(fnNew, fnRef, fileName, fileType):
    isTheSame = 'SUCCESS: python and csh '+fileName+' are the same'
    notTheSame = 'FAIL: python and csh '+fileName+' are different'

    if fileType=='png':
        imageNew = io.imread(fnNew)
        imageRef = io.imread(fnRef)
        # assert imageNew.shape == imageRef.shape, 'Images must be the same shape.'
        ssim_index = ssim(imageNew,imageRef,multichannel=True)
        assert ssim_index > imageSimilarityIndexThreshold, f'{notTheSame} SSM: {ssim_index}'
        print(notTheSame+' no SSIM')

        if imageNew.shape != imageRef.shape:
            print(notTheSame+' image shapes do not match')
    elif fileType=='grd':
        os.system('gmt grdmath '+fnNew+' '+fnRef+' SUB = diff.grd')
        os.system('gmt grdinfo -L2 diff.grd > gmt.log.txt')
        mean = parseCmdOutput('gmt.log.txt', 'mean:')
        stdev = parseCmdOutput('gmt.log.txt', 'stdev:')
        rms = parseCmdOutput('gmt.log.txt', 'rms:')
        #print('Python and csh '+fileName+' "s difference are')
        #print('mean = ',mean, ' stddev = ', stdev, 'rms = ', rms)
        assert 'phase' in fnNew, f'{notTheSame} diff.grd mean={mean} stdev={stdev} rms={rms}'
        assert rms >= fileDiffNumericThreshold, f'{notTheSame} diff.grd mean={mean} stdev={stdev} rms={rms}'
        assert rms >= 0.1, f'{notTheSame} diff.grd mean={mean} stdev={stdev} rms={rms}'
        if (rms<fileDiffNumericThreshold and not ('phase' in fnNew)) or \
                (rms<0.1 and ('phase' in fnNew)):
            print(isTheSame+'; diff.grd mean='+str(mean)+' stdev='+str(stdev)+' rms='+str(rms))
        else:
            print(notTheSame+' diff.grd mean='+str(mean)+' stdev='+str(stdev)+' rms='+str(rms))
        os.system('rm diff.grd gmt.log.txt')

def findErrorsInLogFiles(rootDir):
    errKeyWordList = ['error', 'Error', 'Traceback', 'ERROR']
    for root, dirs, files in os.walk(rootDir):
        for file in files:
            if file=='log.txt':
                with open(os.path.join(root,file),'r') as f:
                    contents = f.read()
                    assert not any(errKeyWord in contents for errKeyWord in errKeyWordList), \
                        f'Error found in {os.path.join(root,file)}'

for caseName in caseNameList:
    print(' ')
    print('Comparing case ', caseName)
    for fileName in fileNameList:
        for path in intfDirList[caseName]:
            refPath  = refRoot+'/'+caseName+'/'+path+'/'+fileName
            testPath = testRoot+'/'+caseName+'/'+path+'/'+fileName
            if os.path.exists(refPath) and os.path.exists(testPath):
                if 'png' in fileName:
                    compare_files(testPath, refPath, fileName, 'png')
                elif 'grd' in fileName:
                    compare_files(testPath, refPath, fileName, 'grd')
    findErrorsInLogFiles(testRoot+'/'+caseName)
