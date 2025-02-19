from typing import Any, Optional, Union

import braille
import brailleInput
import inputCore
import scriptHandler
import speech

from . import callback_manager


class NVDAPatcher(callback_manager.CallbackManager):
	"""Base class to manage patching of braille display changes."""

	def registerSetDisplay(self) -> None:
		braille.displayChanged.register(self.handle_displayChanged)
		braille.displaySizeChanged.register(self.handle_displaySizeChanged)

	def unregisterSetDisplay(self) -> None:
		braille.displaySizeChanged.unregister(self.handle_displaySizeChanged)
		braille.displayChanged.unregister(self.handle_displayChanged)

	def register(self) -> None:
		self.registerSetDisplay()

	def unregister(self) -> None:
		self.unregisterSetDisplay()

	def handle_displayChanged(self, display: Any) -> None:
		self.callCallbacks('set_display', display=display)

	def handle_displaySizeChanged(self, displaySize: Any) -> None:
		self.callCallbacks('set_display', displaySize=displaySize)

class NVDASlavePatcher(NVDAPatcher):
	"""Class to manage patching of synth and braille."""

	def __init__(self) -> None:
		super().__init__()
		self.origSpeak: Optional[Any] = None
		self.orig_pauseSpeech: Optional[Any] = None

	def patchSpeech(self) -> None:
		if self.origSpeak  is not None:
			return
		self.origSpeak = speech._manager.speak
		speech._manager.speak = self.speak
		self.orig_pauseSpeech = speech.pauseSpeech
		speech.pauseSpeech = self.pauseSpeech

	def unpatchSpeech(self):
		if self.origSpeak  is None:
			return
		speech._manager.speak = self.origSpeak
		self.origSpeak = None
		speech.pauseSpeech = self.orig_pauseSpeech
		self.orig_pauseSpeech = None

	def register(self):
		self.patchSpeech()

	def unregister(self):
		self.unpatchSpeech()

	def speak(self, speechSequence: Any, priority: Any) -> None:
		self.callCallbacks('speak', speechSequence=speechSequence, priority=priority)
		self.origSpeak(speechSequence, priority)
		
	def pauseSpeech(self, switch: bool) -> None:
		self.callCallbacks('pause_speech', switch=switch)
		self.orig_pauseSpeech(switch)
		
class NVDAMasterPatcher(NVDAPatcher):
	"""Class to manage patching of braille input."""

	def registerBrailleInput(self) -> None:
		inputCore.decide_executeGesture.register(self.handle_decide_executeGesture)

	def unregisterBrailleInput(self) -> None:
		inputCore.decide_executeGesture.unregister(self.handle_decide_executeGesture)

	def register(self):
		super().register()
		# We do not patch braille input by default

	def unregister(self):
		super().unregister()
		# To be sure, unpatch braille input
		self.unregisterBrailleInput()

	def handle_decide_executeGesture(self, gesture: Union[braille.BrailleDisplayGesture, brailleInput.BrailleInputGesture, Any]) -> bool:
		if isinstance(gesture,(braille.BrailleDisplayGesture,brailleInput.BrailleInputGesture)):
			dict = { key: gesture.__dict__[key] for key in gesture.__dict__ if isinstance(gesture.__dict__[key],(int,str,bool))}
			if gesture.script:
				name=scriptHandler.getScriptName(gesture.script)
				if name.startswith("kb"):
					location=['globalCommands', 'GlobalCommands']
				else:
					location=scriptHandler.getScriptLocation(gesture.script).rsplit(".",1)
				dict["scriptPath"]=location+[name]
			else:
				scriptData=None
				maps=[inputCore.manager.userGestureMap,inputCore.manager.localeGestureMap]
				if braille.handler.display.gestureMap:
					maps.append(braille.handler.display.gestureMap)
				for map in maps:
					for identifier in gesture.identifiers:
						try:
							scriptData=next(map.getScriptsForGesture(identifier))
							break
						except StopIteration:
							continue
				if scriptData:
					dict["scriptPath"]=[scriptData[0].__module__,scriptData[0].__name__,scriptData[1]]
			if hasattr(gesture,"source") and "source" not in dict:
				dict["source"]=gesture.source
			if hasattr(gesture,"model") and "model" not in dict:
				dict["model"]=gesture.model
			if hasattr(gesture,"id") and "id" not in dict:
				dict["id"]=gesture.id
			elif hasattr(gesture,"identifiers") and "identifiers" not in dict:
				dict["identifiers"]=gesture.identifiers
			if hasattr(gesture,"dots") and "dots" not in dict:
				dict["dots"]=gesture.dots
			if hasattr(gesture,"space") and "space" not in dict:
				dict["space"]=gesture.space
			if hasattr(gesture,"routingIndex") and "routingIndex" not in dict:
				dict["routingIndex"]=gesture.routingIndex
			self.callCallbacks('braille_input', **dict)
			return False
		else:
			return True
