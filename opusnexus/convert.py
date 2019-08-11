import opusFC
import h5py
import sys
import opusdictionary
from io import BytesIO
from PIL import Image
import numpy as np

class NXDataHolder:

    def __init__(self):
        self.signal_name = "data"
        self.axes_names = None
        self.signal = None
        self.x = None
        self.y = None
        self.axis = None
        self.rgb = True

def convert(path):
   contents = opusFC.listContents(path)
   opusd = opusdictionary.OpusDict()
   opath = path + "test.nxs"
   name_dict = get_name_dict()

   with h5py.File(opath,'w') as f:
      nxEntry = f.create_group("entry1")
      nxEntry.attrs["NX_class"] = "NXentry"
      for db in contents:
          data = opusFC.getOpusData(path,db)
          if isinstance(data,opusFC.ImageDataReturn):
              add_image_data(nxEntry,data)
          if isinstance(data,opusFC.MultiRegionDataReturn):
              add_multi_data(nxEntry,data)
          if isinstance(data,opusFC.ImageTRCDataReturn):
              add_image_traces(nxEntry,data)
      #nxColl = nxEntry.create_group("parameters")
      #nxColl.attrs["NX_class"] = "NXcollection"
      
      #for k,v in data.parameters.items():
      #   name = k
      #   if (k in opusd):
      #      name = opusd[k]
      #   nxColl.create_dataset(name,data=v)
      images = opusFC.getVisImages(path)
      count = 1;
      for im in images:
          nxe = f.create_group("microscope" +str(count))
          nxe.attrs["NX_class"] = "NXentry"
          add_visible_image(nxe, im)
          count = count + 1

      print("Created file " + opath)

def write_nxdata(nxData, dh):
    nxData.attrs["NX_class"] = "NXdata"
    nxData.attrs["signal"] = dh.signal_name
    nxData.attrs["axes"] = np.string_(dh.axes_names)
    sig = nxData.create_dataset("data",data = dh.signal)
    if dh.axis is not None:
        nxData.create_dataset(dh.axes_names[-1], data = dh.axis)
    
    if dh.rgb:
        sig.attrs["interpretation"] = "rgba-image"
    nxData.create_dataset("stage_y", data = dh.y)
    nxData.create_dataset("stage_x", data = dh.x)



def add_image_traces(group,image_trc_data):
    traces = image_trc_data.traces
    
    for i in range(traces.shape[2]):
        t = traces[:,:,i].squeeze()
        nxd = NXDataHolder()
        nxd.axes_names = ["stage_y", "stage_x"]
        nxd.signal = t
        nxd.x = image_trc_data.mapX
        nxd.y = image_trc_data.mapY
        nxd.rgb = False
        nxData = group.create_group("map" + str(i+1))
        write_nxdata(nxData, nxd)

def add_image_data(group, image_data):
    name = image_data.dataType
    name_dict = get_name_dict()
    if name in name_dict:
        name = name_dict[name]

    data_axis = "data_axis"

    if "DXU" in image_data.parameters:
        data_axis = image_data.parameters['DXU']
    
    nxd = NXDataHolder()
    nxd.axes_names = ["stage_y", "stage_x", data_axis]
    nxd.signal = image_data.spectra
    nxd.x = image_data.mapX
    nxd.y = image_data.mapY
    nxd.rgb = False
    nxd.axis = image_data.x

    nxData = group.create_group(name)
    write_nxdata(nxData, nxd)
    nxs = NXDataHolder()

    nxs.axes_names = ["stage_y", "stage_x"]
    nxs.signal = image_data.spectra.sum(axis=2)
    nxs.x = image_data.mapX
    nxs.y = image_data.mapY
    nxs.rgb = False
    
    nxData = group.create_group(name + "_sum")
    write_nxdata(nxData, nxs)

def add_single_data(group, single_data):
    pass

def add_multi_data(group, multi_data):
    name = multi_data.dataType
    name_dict = get_name_dict()
    if name in name_dict:
        name = name_dict[name]

    data_axis = "data_axis"

    if "DXU" in multi_data.parameters:
        data_axis = multi_data.parameters['DXU']
    
    count = 1
    for r in multi_data.regions:
        write_region(group,r,count,name,data_axis,multi_data.x)

def write_region(group,region,count,name,data_axis,xaxis):
    
    shape = get_shape(region.mapX)

    
    axes_names = ["stage_y", "stage_x", data_axis] if shape is not None else ["stage_x", data_axis]
    
    x = region.mapX
    y = region.mapY
    spectra = region.spectra
    ssum = spectra.sum(axis=(spectra.ndim-1))
    if shape is not None:
        spectra,x,y,ssum = reshape_data(spectra,x,y,ssum,shape)

    nxd = NXDataHolder()
    nxd.axes_names = axes_names
    nxd.signal = spectra
    nxd.x = x
    nxd.y = y
    nxd.rgb = False
    nxd.axis = xaxis

    nxData = group.create_group(name + str(count))
    write_nxdata(nxData, nxd)
    nxs = NXDataHolder()
    
    axes_names = ["stage_y", "stage_x"] if shape is not None else ["stage_x"]

    nxs.axes_names = axes_names
    nxs.signal = ssum
    nxs.x = x
    nxs.y = y
    nxs.rgb = False
    
    nxData = group.create_group(name + str(count) + "_sum")

    write_nxdata(nxData, nxs)

def reshape_data(spectra,x,y,ssum,shape):
    spectra = spectra.reshape(shape[0],shape[1],-1)
    ssum = ssum.reshape(shape)
    x = x.reshape(shape)[0,:].squeeze()
    y = y.reshape(shape)[:,0].squeeze()
    return spectra,x,y,ssum

def add_multi_traces(group, multi_trc_data):
    pass

def add_visible_image(group, vis_data):
    nxData = group.create_group("image")
    data = vis_data['image']
    byte_file = BytesIO(data)
    image = Image.open(byte_file)
    print(vis_data["Pos. Y"])
    print(vis_data["Pos. X"])
    yPos = vis_data["Pos. Y"]
    yPixel = vis_data["PixelSizeY"]
    ySize = vis_data["Size Y"]
    xPos = vis_data["Pos. X"]
    xPixel = vis_data["PixelSizeX"]
    xSize = vis_data["Size X"]

    nxd = NXDataHolder()
    nxd.axes_names = [".","stage_y", "stage_x"]
    nxd.signal = np.asarray(image).transpose((2,0,1))
    nxd.x = xPos*xPixel + np.arange(xSize)*xPixel
    nxd.y = (yPos*yPixel + np.arange(ySize)*yPixel)[::-1]
    nxd.rgb = True
    write_nxdata(nxData, nxd)



def get_name_dict():
    return {"AB" : "absorbance",
            "RSC" : "reference_single_channel",
            "SSC" : "sample_single_channel",
            "SIFG" : "sample_interferogram",
            "RIFG" : "reference_interferogram"}

def get_shape(x):
    dx = x[0:-1] - x[1:]
    ddx = dx[0:-1] - dx[1:]
    steps = np.argwhere(ddx > 0.001) +1
    if (x.size == (steps[0][0] * (len(steps)+1))):
        return [len(steps)+1, steps[0][0]]

    return None


if __name__ == "__main__":
   for arg in sys.argv[1:]:
      convert(arg)
