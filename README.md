# 3D Viewer for Microscopy 

Project Description:
This is an image viewer for 2D/3D images produced from spinning disc/confocal/lightsheet/etc microscopy.  This viewer is designed primarily for viewing 3D images in a plane by plane view, where the axis of view can be changed.  2D images can also be viewed.  You can load the proprietary file format sldy (made by Intelligent Imaging Innovations) along with TIFF/TIF, JPEG, and PNG.  This application was created using node.js, React, Vite, and Python.  There two demo images available for download from the Github.  The first being a sldy file showing myoepithelial cells from breast tissue.  This image was produced by Intelligent Imaging Innovations and Jen Monks.  The second image is a TIFF showing colonic epithelial cells produced by Atsuo Nakamura from the Whitehead Institute for Biomedical Research, available on BioImage Archive S-BSST59.           

## Running Instructions 
There are two scripts for this project, a frontend and a backend.  The frontend script is responsible for the web view of this app and the backend is responsible for reading the sldy files, handling the annotations (saving/undoing/redoing/exporting), and performing the calculations required to produce a global histogram.  The frontend script sets up the webview of the app.  In order to run, the backend script must be started first.  

In a terminal of your choice, cd into the directory where the folder labeled backend is being stored, then type python app.py and run the command.  This will start the backend server.  Next, in a second terminal, cd into the folder labeled ml3_project and type npm run dev and this will produce a server to put enter into a web browser.  Copy this into a web browser to see the image viewer.    

## Major Libraries/Frameworks Used (non exhaustive- most important listed)
Frontend: 
-React: Responsible for the UI and shows responses when the user interacts with file selection, zoom, brushes, and other buttons.  
-Vite: Dev server shows live changes of the jsx script in the web browser
Backend:
-Flask: Flask handles are the incoming requests from the web viewer.  This allows undo/redo, image annotation, and export to occur
-NumPy: Images are stored as NumPy arrays, computes the histograms, and allows for image slicing on various axis
-Tifffile and SBReadFile: Libraries used for reading image file formats
-SQLite3- responsible for communicating with the database that stores the annotations, the layers, and undo/redo history
-SQLite-database that stores annotations, layer info (name/color/order), and undo/redo history

## Features
This image viewer inclued:
-Load from local file system
-Drop down image list
-Multiple axis views
-Zoom
-Plane Slider and Arrows 
-Interactive histogram that makes live adjustments
-Annotations are enabled with tools including brush, flood fill, eraser
-Size adjustment on brush and eraser
-Multiple layers for labeling different structures
-Undo/Redo
-Clear layer button
-Export layers as tiff

## Extra Credit
Annotations are implemented, a database is implemented to store annotation actions shown through undo/redo feature

