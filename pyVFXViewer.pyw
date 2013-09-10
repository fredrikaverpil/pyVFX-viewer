''' Run mode '''
''' ------------- '''
runMode = 'standalone'
try:
	import maya.cmds as cmds
	import maya.OpenMayaUI as omui
	import shiboken
	runMode = 'maya'
except:
	pass
try:
	import nuke
	from nukescripts import panels
	runMode = 'nuke'	
except:
	pass


''' Imports regardless of Qt type '''
''' ------------------------------ '''
import os, sys, time
import xml.etree.ElementTree as xml
from cStringIO import StringIO




''' PySide or PyQt - that is the question... '''
''' ---------------------------------------- '''
QtType = 'PySide'	# Edit this to switch between PySide and PyQt
if QtType == 'PySide':
	from PySide import QtCore, QtGui, QtUiTools
	if (runMode == 'nuke'):
		print 'Make sure to have pysideuic somewhere in your PYTHONPATH'
		#sys.append.path('//10.0.0.1/share/path/to/pysideuic')
	import pysideuic	
elif QtType == 'PyQt':
	from PyQt4 import QtCore, QtGui, uic
	import sip




''' Variables '''
print 'This app is now using ' + QtType
uiFile = os.path.join(os.path.dirname(__file__), "mainWindow.ui")
windowTitle = 'pyVFX Viewer'
windowObject = 'pyVFXViewer'




class PyQtPySideFixer(QtGui.QMainWindow):
	def __init__(self, parent=None):
		"""Super, loadUi, signal connections"""
		super(PyQtPySideFixer, self).__init__(parent)
		print 'Making a detour (hack), necessary for when using PyQt'


def loadUiType(uiFile):
	"""
	Pyside lacks the "loadUiType" command, so we have to convert the ui file to py code in-memory first
	and then execute it in a special frame to retrieve the form_class.
	"""
	parsed = xml.parse(uiFile)
	widget_class = parsed.find('widget').get('class')
	form_class = parsed.find('class').text

	with open(uiFile, 'r') as f:
		o = StringIO()
		frame = {}

		if QtType == 'PySide':
			pysideuic.compileUi(f, o, indent=0)
			pyc = compile(o.getvalue(), '<string>', 'exec')
			exec pyc in frame

			#Fetch the base_class and form class based on their type in the xml from designer
			form_class = frame['Ui_%s'%form_class]
			base_class = eval('QtGui.%s'%widget_class)
		elif QtType == 'PyQt':
			form_class = PyQtPySideFixer
			base_class = QtGui.QMainWindow
	return form_class, base_class
form, base = loadUiType(uiFile)



def wrapinstance(ptr, base=None):
	"""
	Utility to convert a pointer to a Qt class instance (PySide/PyQt compatible)

	:param ptr: Pointer to QObject in memory
	:type ptr: long or Swig instance
	:param base: (Optional) Base class to wrap with (Defaults to QObject, which should handle anything)
	:type base: QtGui.QWidget
	:return: QWidget or subclass instance
	:rtype: QtGui.QWidget
	"""
	if ptr is None:
		return None
	ptr = long(ptr) #Ensure type
	if globals().has_key('shiboken'):
		if base is None:
			qObj = shiboken.wrapInstance(long(ptr), QtCore.QObject)
			metaObj = qObj.metaObject()
			cls = metaObj.className()
			superCls = metaObj.superClass().className()
			if hasattr(QtGui, cls):
				base = getattr(QtGui, cls)
			elif hasattr(QtGui, superCls):
				base = getattr(QtGui, superCls)
			else:
				base = QtGui.QWidget
		return shiboken.wrapInstance(long(ptr), base)
	elif globals().has_key('sip'):
		base = QtCore.QObject
		return sip.wrapinstance(long(ptr), base)
	else:
		return None


def maya_main_window():
	main_window_ptr = omui.MQtUtil.mainWindow()
	return wrapinstance( long( main_window_ptr ), QtGui.QWidget )	# Works with both PyQt and PySide


def runStandalone():
	app = QtGui.QApplication(sys.argv)
	global gui
	gui = MediaViewer()
	gui.show()
	sys.exit(app.exec_())

def runMaya():
	if cmds.window(windowObject, q=True, exists=True):
		cmds.deleteUI(windowObject)
	global gui
	gui = MediaViewer( maya_main_window() )
	gui.show()

def runNuke():
	# BIG PROBLEM NEEDS FIXING: global gui object not created for Nuke, breaks progress bar
	#pane = nuke.getPaneFor('Properties.1')
	#panels.registerWidgetAsPanel('mediaViewer', 'Media Viewer', 'uk.co.thefoundry.NukeTestWindow', True).addToPane(pane) # View pane and add it to panes menu
	global gui
	gui = MediaViewer()
	gui.show




class MediaViewer(form, base):
	def __init__(self, parent=None):
		"""Super, loadUi, signal connections"""
		super(MediaViewer, self).__init__(parent)

		if QtType == 'PySide':
			print 'Loading UI using PySide'
			self.setupUi(self)

		elif QtType == 'PyQt':
			print 'Loading UI using PyQt'
			uic.loadUi(uiFile, self)

		self.setObjectName(windowObject)
		self.setWindowTitle(windowTitle)



		# Directories
		self.cacheDir = os.path.join( os.path.dirname(__file__), 'cache' )
		if not os.path.exists(self.cacheDir):
			os.makedirs(self.cacheDir)
		self.scanDir = ''
		self.currentDir = '/Volumes/1TBDrive/Users/fredrik/Pictures/2013'		# dev
		if not os.path.isdir(self.currentDir):
			self.currentDir = os.path.dirname(__file__)
		self.cacheDir = os.path.join( os.path.dirname(__file__), 'cache')

		# Format support
		self.formatSupport = ['bmp','gif','jpg','jpeg','png','pbm','pgm','ppm','tiff','tif','xbm','xpm']	# Supported by QImage (Read)
		self.log = []

		# Thumbnails size
		self.thumbnailHeight = 200
		
		# Pagination
		self.itemsToLoad = 50

		# Load settings
		self.settingsGet()


		self.progressBar.setValue(0) # Goes between 0-100
		self.listDirs()


		self.listWidgetDirs.itemClicked.connect( self.listImagery )					# Select folder in list
		self.tabWidget.tabCloseRequested.connect( self.closeTab )					# Close tab
		self.tabWidget.currentChanged.connect( self.updateOnTabChange )			# Update stuff whenever we select another tab
		self.checkBoxScanSubdirs.stateChanged.connect( self.updateTabContents )				# Update current tab to scan subdirs or not scan subdirs



		# Somehow this magically enables a statusbar...
		#self.statusBar()

		# File menu
		#self.exitAction.triggered.connect( QtGui.qApp.quit )
		self.actionChangeDir.triggered.connect( self.changeDir )



	def closeEvent(self, event):
		self.settingsSet()

	def settingsSet(self):
		window = self.geometry()
		
		settings = QtCore.QSettings("pyVFX", "Media Viewer")
		settings.beginGroup("Media Viewer");
		settings.setValue("window", window);
		settings.endGroup();

	def settingsGet(self):
		# Fetch settings
		try:
			settings = QtCore.QSettings("pyVFX", "Media Viewer")
			settings.beginGroup("Media Viewer")			
			window = settings.value("window")
			settings.endGroup()

			if QtType == 'PySide':
				self.setGeometry( window )
			elif QtType == 'PyQt':
				self.setGeometry( window.toRect() )

		except:
			pass


	
	def updateTabContents(self):
		self.tabWidget.blockSignals(True)
		# To do: check if we have a tab open or not...
		if self.checkBoxScanSubdirs.checkState() == self.tabWidget.currentWidget().subdirs:
			# All good
			pass
		else:
			# Wipe contents (remove tab) and scan with subdirs activated
			self.progressBar.setValue(0)

			# Since the listImagery method reads the position in the listWidgetsDir, it is necessary
			# to move the selection to this row before removing the tab.
			tabName = self.tabWidget.currentWidget().scanDir[self.tabWidget.currentWidget().scanDir.rfind('/')+1 : len(self.tabWidget.currentWidget().scanDir) ]
			for x in range(0, self.listWidgetDirs.count() ):
				#print self.listWidgetDirs.item(x).text().encode('ascii', 'ignore')
				if self.listWidgetDirs.item(x).text() == tabName:
					self.listWidgetDirs.setCurrentRow(x)

			# Remove tab
			self.tabWidget.removeTab( self.tabWidget.indexOf( self.tabWidget.currentWidget()) )


			# Re-create the tab
			self.listImagery()
		self.tabWidget.blockSignals(False)

			

	def updateOnTabChange(self):
		# Check to see whether we have deleted all tabs or not
		skip = False
		try:
			self.tabWidget.currentWidget().maxProgress
		except:
			skip = True
			self.progressBar.reset()

		if not skip:
			minimum = 0
			maximum = self.tabWidget.currentWidget().maxProgress
			current = self.tabWidget.currentWidget().currentProgress
			
			self.updateProgress(minimum, maximum, current)


			if self.checkBoxScanSubdirs.checkState() == self.tabWidget.currentWidget().subdirs:
				# Do not change checkbox
				pass
			else:
				# Changing checkbox value
				self.checkBoxScanSubdirs.blockSignals(True)
				if self.tabWidget.currentWidget().subdirs:
					self.checkBoxScanSubdirs.setCheckState( QtCore.Qt.Checked )
					QtGui.QApplication.processEvents()
				else:
					self.checkBoxScanSubdirs.setCheckState( QtCore.Qt.Unchecked )
					QtGui.QApplication.processEvents()
				self.checkBoxScanSubdirs.blockSignals(False)
		
		try:
			self.scanDir = self.tabWidget.currentWidget().scanDir
		except:
			pass
		


	def updateProgress(self, minimum, maximum, current):
		if current == maximum:
			self.progressBar.reset()
		else:
			self.progressBar.setMinimum( minimum )
			self.progressBar.setMaximum( maximum )
			self.progressBar.setValue( current )
			QtGui.QApplication.processEvents()
			




	def changeDir(self):
		fileDialog = QtGui.QFileDialog()
		folderName = fileDialog.getExistingDirectory(None, "Select Folder")
		if folderName != '':
			self.currentDir = folderName
			self.listDirs()


	def closeTab(self, index):
		self.tabWidget.removeTab(index)	

	def logList(self, logList):
		count = 0
		for line in logList:
			self.log.append(line)
			count += 1
			if count == len(logList):
				self.lineEditInfo.setText(line)

	def listDirs(self):
		self.listWidgetDirs.clear()
		dirs = os.walk( self.currentDir ).next()[1]
		for dir in dirs:
			#dirUnicode = u'' + dir + ''
			self.listWidgetDirs.addItem( dir )


		

	def listImagery(self):

		self.scanDir = os.path.join( self.currentDir, str(self.listWidgetDirs.currentItem().text()) )

		if self.checkBoxScanSubdirs.isChecked():
			dirs = [x[0] for x in os.walk( self.scanDir )]
		else:
			dirs = []
			dirs.append(self.scanDir)

		imageFiles = []
		for dir in dirs:
			for file in os.listdir ( dir ):
				for format in self.formatSupport:
					if file.lower().endswith( format ):
						imageFiles.append( os.path.join( dir, file) )
		 
		if len(imageFiles) == 0:
			self.logList( ['Found 0 files in \"' + self.listWidgetDirs.currentItem().text() + '\".'] )
		else:	
			self.logList( ['Found a total of ' + str( len(imageFiles) ) + ' files in \"' + self.listWidgetDirs.currentItem().text() + '\".'] )
			self.createTab(imageFiles)


	def checkForExistingTab(self):
		retVal = False
		for x in range( 0, gui.tabWidget.count() ):
			#print 'COMPARING ' + self.scanDir + ' against ' + gui.tabWidget.widget(x).scanDir
			if (self.scanDir == gui.tabWidget.widget(x).scanDir):
				retVal = True
		return retVal


	def createTab(self, imageFiles):
		# Check to see whether the scanDir is already present inside any of the tab widgets
		scanDirFound = self.checkForExistingTab()

		if scanDirFound:
			
			# Open existing tab
			for x in range( 0, gui.tabWidget.count() ):
				if gui.scanDir == gui.tabWidget.widget(x).scanDir:
					gui.tabWidget.setCurrentIndex(x)
			
		
		else:
			
			# Create new tab
			newTab = Tab(self, imageFiles)
			#self.tabList.append(tab)
			self.tabWidget.addTab( newTab, self.listWidgetDirs.currentItem().text() )
			self.tabWidget.setCurrentIndex( self.tabWidget.count()-1 )
			QtGui.QApplication.processEvents()

			newTab.associatedTab = self.tabWidget.currentWidget()
			newTab.loadImagery()






class ThreadLoadImage(QtCore.QThread):
	def __init__(self, parent, placeholder, imageFilepath):
		super(ThreadLoadImage, self).__init__(parent)
		#QtCore.QThread.__init__(self)
		
		self.placeholder = placeholder
		self.imageFilepath = imageFilepath
	



	def run(self):
		proxyFilename = self.imageFilepath.replace('/','-').replace('\\','-').replace(':','')
		proxyFilepath = os.path.join(gui.cacheDir, proxyFilename)

		# Get "last modified" date of original full-res imagery
		(mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat( self.imageFilepath )
		#print "fullres last modified: %s" % time.ctime(mtime)
		atimeFullres = atime
		mtimeFullres = mtime



		# Get "last modified" date of proxy image
		if os.path.exists( proxyFilepath ):
			(mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat( proxyFilepath )
			#print "proxy last modified: %s" % time.ctime(mtime)
			atimeProxy = atime
			mtimeProxy = mtime
		else:
			atimeProxy = None
			mtimeProxy = None



		if os.path.exists( proxyFilepath ) and (mtimeFullres == mtimeProxy):
			# Cache exists, contains same "last modified date" as fullres -- so load that instead
			self.placeholder.image.load( proxyFilepath )
			self.placeholder.scaledImage = self.placeholder.image.scaledToHeight(200, QtCore.Qt.SmoothTransformation)	
			del self.placeholder.image

		else:
			# Cache does not exist, load full res and save proxy image
			self.placeholder.image.load( self.imageFilepath )
			self.placeholder.scaledImage = self.placeholder.image.scaledToHeight(200, QtCore.Qt.SmoothTransformation)	
			del self.placeholder.image

			# Save cache image
			jpegWriter = QtGui.QImageWriter()
			jpegWriter.setFileName( proxyFilepath )
			jpegWriter.write(self.placeholder.scaledImage)

			# Make proxy carry the same "last modified" date as the fullres imagery
			os.utime( proxyFilepath, (atime, mtime) )
		

		

		
		

		self.emit( QtCore.SIGNAL('update(QString)'), "image loaded" )
		return





class Thumbnail(QtGui.QWidget):
	def __init__(self, parent=None, module='', imageFilepath=''):
		super(Thumbnail, self).__init__(parent)

		self.placeholder = module
		self.imageFilepath = imageFilepath

		self.parentTab = parent
		self.associatedTab = parent.associatedTab

		
		
		
		# If tab associated with this process is the current one in the GUI, show the progress
		if self.associatedTab == gui.tabWidget.currentWidget():
			minimum = 0
			maximum = self.parentTab.maxProgress
			current = self.parentTab.currentProgress
			#gui.updateProgress(minimum, maximum, current)



		#gui.logList( ['Loading fullres image for ' + self.placeholder.textLabel.text() ])

		self.placeholder.image = QtGui.QImage(200, gui.thumbnailHeight, QtGui.QImage.Format_ARGB32)
		
		
		# Threading
		self.workThread = ThreadLoadImage(self, self.placeholder, self.imageFilepath)
		self.connect( self.workThread, QtCore.SIGNAL("update(QString)"), self.next )
		self.workThread.start()
		
	
	def next(self):
		self.placeholder.layout.removeWidget(self.placeholder.imageLabel)
		self.placeholder.layout.removeWidget(self.placeholder.textLabel)

		self.placeholder.imageLabel.setParent(None)		# Prevent the placeholders to show up
		self.placeholder.textLabel.setParent(None)

		self.placeholder.imageLabel = QtGui.QLabel('')
		self.placeholder.imageLabel.setPixmap(QtGui.QPixmap.fromImage( self.placeholder.scaledImage ))

		self.placeholder.layout.addWidget( self.placeholder.imageLabel )
		self.placeholder.layout.addWidget( self.placeholder.textLabel )

		# Update progress bar
		self.parentTab.currentProgress += 1
		if self.associatedTab == gui.tabWidget.currentWidget():
			minimum = 0
			maximum = self.parentTab.maxProgress
			current = self.parentTab.currentProgress
			gui.updateProgress(minimum, maximum, current)

		

		
		
	




class Placeholder(QtGui.QWidget):
	def __init__(self, parent=None, imageFilepath=''):
		super(Placeholder, self).__init__(parent)
		

		self.layout = QtGui.QVBoxLayout(self)
		

		# Create place holder
		self.image = QtGui.QImage(200, 200, QtGui.QImage.Format_ARGB32)
		self.image.fill(QtGui.qRgb(255,0,0))

		self.imageLabel = QtGui.QLabel('')
		self.imageLabel.setPixmap(QtGui.QPixmap.fromImage( self.image ))

		# Create text label
		self.textLabel = QtGui.QLabel( os.path.basename(imageFilepath) )

		# Attach image and text to widget
		self.layout.addWidget( self.imageLabel )
		self.layout.addWidget( self.textLabel )

		
		


class Tab(QtGui.QWidget):
	def __init__(self, parent=None, imageFiles=['']):
		super(Tab, self).__init__(parent)


		self.widget_layout = QtGui.QVBoxLayout(self)
		self.scrollarea = QtGui.QScrollArea()
		self.scrollarea.setWidgetResizable(True)
		self.widget_layout.addWidget(self.scrollarea)
		self.widget = QtGui.QWidget()
		#self.layout = QtGui.QVBoxLayout(self.widget)
		self.layout = FlowLayout(self.widget)
		self.scrollarea.setWidget(self.widget)
		self.layout.setAlignment(QtCore.Qt.AlignLeft)

		# The imagery associated with this tab (and which have not yet been loaded)
		self.scanDir = gui.scanDir
		self.imageFiles = imageFiles

		# Subdirs included or not
		self.subdirs = False
		if gui.checkBoxScanSubdirs.isChecked():
			self.subdirs = True

		self.removed = False

		self.associatedTab = ''

		# Prepare progress bar
		self.currentProgress = 0
		self.maxProgress = len(self.imageFiles)

		# Pagination variables for this tab
		self.pagesShown = 1

		# Pagination signal
		self.scrollarea.verticalScrollBar().valueChanged.connect( self.paginationLoadNextItems )

	def paginationLoadNextItems(self):
		sliderMax = self.scrollarea.verticalScrollBar().maximum()
		sliderPos = self.scrollarea.verticalScrollBar().sliderPosition()
		
		if len(self.imageFiles) != 0:
			if sliderPos == sliderMax:
				self.pagesShown += 1
				self.loadImagery()

	

	def loadImagery(self):
		imageFilesPage = self.imageFiles

		# Create a module for each imagery as well as placeholder
		self.moduleList = []
		countPagination = 1
		for imageFilepath in imageFilesPage:
			if (countPagination <= gui.itemsToLoad ):
				newModule = Placeholder(self, imageFilepath)			# Create a new ui module
				self.moduleList.append(newModule)						# Put it in the list of modules
				self.layout.addWidget( newModule )          			# Add this module ui widget to 'modLayout'
			countPagination += 1



		# Initiate threading, loading data, working, crunching...
		countModule = 0
		countPagination = 1
		for imageFilepath in imageFilesPage:
			if (countPagination <= gui.itemsToLoad ):
				newModule = self.moduleList[countModule]
				Thumbnail(self, newModule, imageFilepath )		# Load imagery, preform processing etc...
				countModule += 1
			countPagination += 1




		# Remove the already loaded files from the list of files to load (auto scroll)
		totalSize = len(self.imageFiles)
		if totalSize < gui.itemsToLoad:
			numberOfItemsToRemove = totalSize
		else:
			numberOfItemsToRemove = gui.itemsToLoad

		for x in range(0, numberOfItemsToRemove):
				#print 'Removing ' + os.path.basename(imageFilepath) + ' from self.imageFiles list...'
				self.imageFiles.pop(0)
		


		if len(self.imageFiles) == 0:
			gui.progressBar.reset()
		
			


class FlowLayout(QtGui.QLayout):
	def __init__(self, parent=None, margin=0, spacing=-1):
		super(FlowLayout, self).__init__(parent)

		if parent is not None:
			self.setMargin(margin)

		self.setSpacing(spacing)

		self.itemList = []

	def setMargin(self, margin):
		pass

	def __del__(self):
		item = self.takeAt(0)
		while item:
			item = self.takeAt(0)

	def addItem(self, item):
		self.itemList.append(item)

	def count(self):
		return len(self.itemList)

	def itemAt(self, index):
		if index >= 0 and index < len(self.itemList):
			return self.itemList[index]

		return None

	def takeAt(self, index):
		if index >= 0 and index < len(self.itemList):
			return self.itemList.pop(index)

		return None

	def expandingDirections(self):
		return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

	def hasHeightForWidth(self):
		return True

	def heightForWidth(self, width):
		height = self.doLayout(QtCore.QRect(0, 0, width, 0), True)
		return height

	def setGeometry(self, rect):
		super(FlowLayout, self).setGeometry(rect)
		self.doLayout(rect, False)

	def sizeHint(self):
		return self.minimumSize()

	def minimumSize(self):
		size = QtCore.QSize()

		for item in self.itemList:
			size = size.expandedTo(item.minimumSize())

		#size += QtCore.QSize(2 * self.margin(), 2 * self.margin())
		return size

	def doLayout(self, rect, testOnly):
		x = rect.x()
		y = rect.y()
		lineHeight = 0

		for item in self.itemList:
			wid = item.widget()
			spaceX = self.spacing() + wid.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton, QtCore.Qt.Horizontal)
			spaceY = self.spacing() + wid.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton, QtCore.Qt.Vertical)
			nextX = x + item.sizeHint().width() + spaceX
			if nextX - spaceX > rect.right() and lineHeight > 0:
				x = rect.x()
				y = y + lineHeight + spaceY
				nextX = x + item.sizeHint().width() + spaceX
				lineHeight = 0

			if not testOnly:
				item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

			x = nextX
			lineHeight = max(lineHeight, item.sizeHint().height())

		return y + lineHeight - rect.y()


if runMode == 'standalone':
	runStandalone()
elif runMode == 'maya':
	runMaya()
elif runMode == 'nuke':
	runNuke()
