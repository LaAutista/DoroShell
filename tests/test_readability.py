"""Contrast checks on the actual shipped styles, including gradient endpoints."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shiboken6
from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtWidgets import QApplication
from menu.start_menu import StartMenu
from settings import Settings


def luminance(color):
    rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))


def contrast(first,second):
    low,high=sorted((luminance(first),luminance(second)))
    return (high+.05)/(low+.05)


def rule(css,selector):
    return re.search(re.escape(selector)+r'\s*\{([^}]+)\}',css).group(1)


def text_color(block):
    return re.search(r'(?:^|;)\s*color:\s*(#[0-9a-f]{6})',block).group(1)


def backgrounds(block):
    value=re.search(r'(?:^|;)\s*background:\s*([^;]+)',block).group(1)
    return re.findall(r'#[0-9a-f]{6}',value)


class ReadabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def check_pair(self,foreground,backgrounds):
        self.assertTrue(backgrounds)
        for background in backgrounds:
            self.assertGreaterEqual(contrast(foreground,background),4.5,(foreground,background))

    def test_menu_and_settings_states(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp,'XDG_DATA_HOME':tmp}):
            menu=StartMenu();settings=Settings(Path(tmp))
            try:
                css=menu.styleSheet();ink=text_color(rule(css,'QWidget'))
                for selector in ('QWidget#applicationsPanel','QListWidget, QLineEdit, QComboBox','QListWidget::item:selected','QPushButton:hover, QPushButton:focus','QMenu','QMessageBox','QMessageBox QPushButton'):
                    self.check_pair(ink,backgrounds(rule(css,selector)))
                places=text_color(rule(css,'QWidget#placesPanel QLabel, QWidget#placesPanel QPushButton'))
                for selector in ('QWidget#placesPanel','QWidget#placesPanel QPushButton:hover, QWidget#placesPanel QPushButton:focus','QPushButton[sessionPrimary="true"]','QPushButton#powerMenuArrow'):
                    self.check_pair(places,backgrounds(rule(css,selector)))
                placeholder=re.search(r'placeholder-text-color:\s*(#[0-9a-f]{6})',css).group(1)
                self.check_pair(placeholder,backgrounds(rule(css,'QListWidget, QLineEdit, QComboBox')))
                popup=rule(css,'QComboBox QAbstractItemView');self.check_pair(text_color(popup),backgrounds(popup))
                css=settings.styleSheet();ink=text_color(rule(css,'QWidget'))
                for selector in ('QWidget#doroShellSettings','QComboBox, QLineEdit','QPlainTextEdit','QPushButton','QPushButton:hover, QPushButton:focus','QListWidget','QListWidget::item:selected','QListWidget::item:hover'):
                    self.check_pair(ink,backgrounds(rule(css,selector)))
                disabled=rule(css,'QPushButton:disabled');self.check_pair(text_color(disabled),backgrounds(disabled))
                self.check_pair(text_color(rule(css,'QComboBox QAbstractItemView::item:disabled')),backgrounds(rule(css,'QComboBox QAbstractItemView')))
                popup=rule(css,'QComboBox QAbstractItemView');self.check_pair(text_color(popup),backgrounds(popup))
            finally:
                shiboken6.delete(menu);shiboken6.delete(settings)

    def test_native_panel_text_across_gloss_gradient(self):
        patch_text=(Path(__file__).resolve().parents[1]/'panel/patches/0001-hidden-tray-popup.patch').read_text()
        line=next(line for line in patch_text.splitlines() if line.startswith('+') and 'QLabel#WorldClockContent,' in line)
        ink=re.search(r'color: (#[0-9a-f]{6})',line).group(1)
        gradient=next(line for line in patch_text.splitlines() if line.startswith('+') and 'LXQtPanel #BackgroundWidget { background: qlineargradient' in line)
        self.check_pair(ink,re.findall(r'stop:[0-9.]+ (#[0-9a-f]{6})',gradient))

    def test_dark_palette_dropdown_selection_and_system_font(self):
        old_palette=self.app.palette();old_font=self.app.font()
        dark=QPalette(old_palette)
        for role in (QPalette.ColorRole.Window,QPalette.ColorRole.Base,QPalette.ColorRole.Highlight):
            dark.setColor(role,QColor('#202020'))
        self.app.setPalette(dark)
        large=QFont(old_font);large.setPointSize(16);self.app.setFont(large)
        try:
            with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp,'XDG_DATA_HOME':tmp}):
                for window in (StartMenu(),Settings(Path(tmp))):
                    try:
                        combo=window.category if isinstance(window,StartMenu) else window.choices['menu']
                        window.show();self.app.processEvents()
                        self.assertEqual(combo.font().pointSize(),16)
                        if isinstance(window, StartMenu): window.programs.click()
                        combo.showPopup();self.app.processEvents()
                        view=combo.view();rect=view.visualRect(view.model().index(0,0))
                        rendered=view.viewport().grab().toImage()
                        background=rendered.pixelColor(rect.right()-8,rect.center().y()).name()
                        self.check_pair('#351329',[background])
                        combo.hidePopup();window.close()
                    finally:shiboken6.delete(window)
        finally:
            self.app.setPalette(old_palette);self.app.setFont(old_font)
