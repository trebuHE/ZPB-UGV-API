from PySide6.QtCore import QThread, Signal

class APIWorker(QThread):
	'''QThread for running API Calls asynchronusly'''
	finished = Signal(dict)
	error = Signal(str)

	def __init__(self, api_callable, *args, **kwargs):
		super().__init__()
		self.api_callable = api_callable
		self.args = args
		self.kwargs = kwargs
	
	def run(self):
		try:
			result = self.api_callable(*self.args, **self.kwargs)
			self.finished.emit(result)
		except Exception as e:
			self.error.emit(str(e))