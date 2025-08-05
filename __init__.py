# Blender add-on: detect active modal operators that may prevent autosave
# Copyright (C) 2025 Spencer Magnusson

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from datetime import datetime
import inspect
import os
import subprocess
import sys
import tempfile

import bpy

modal_operators = dict()


class RemoveModalOperator(bpy.types.Operator):
    """Removes modal operator from display"""
    bl_idname = 'wm.remove_modal_from_display'
    bl_label = 'Remove Modal Operator'

    name: bpy.props.StringProperty()

    def execute(self, context):
        global modal_operators
        if not self.name:
            self.report({'ERROR'}, 'No operator selected')
            return {'CANCELLED'}

        for op_name in modal_operators.keys():
            if op_name == self.name:
                modal_operators.pop(op_name)
                break
        
        return {'FINISHED'}


class OpenFileDirectory(bpy.types.Operator):
    """Opens containing directory of modal operator module in file manager"""
    bl_idname = 'wm.reveal_modal_in_file_manager'
    bl_label = 'Reveal in File Manager'

    filepath: bpy.props.StringProperty()

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, 'No file selected')
            return {'CANCELLED'}

        path = self.filepath
        if sys.platform == 'win32':
            subprocess.run('explorer.exe /select,\"{}\"'.format(path))
            print('explorer.exe /select,\"{}\"'.format(path))
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        elif sys.platform.startswith("linux"):
            subprocess.run(['xdg-open', path])
        else:
            raise OSError(f'Unsupported operating system: {sys.platform}')
        
        return {'FINISHED'}


class OpenFileInEditor(bpy.types.Operator):
    """Opens Python module containing modal operator in Blender's text editor"""
    bl_idname = 'wm.open_modal'
    bl_label = 'Open modal operator module'

    filepath: bpy.props.StringProperty()

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, 'No file selected')
            return {'CANCELLED'}

        bpy.data.texts.load(self.filepath)

        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.filepath:
            self.report({'ERROR'}, 'No file selected')
            return {'CANCELLED'}

        text = bpy.data.texts.load(self.filepath)
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces[0].text = text
                break
        
        return {'FINISHED'}


class ModalOperatorPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_modal_ops'
    bl_label = 'Active Modal Operators'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'View'

    def _get_matching_autosave_file_timestamp(self, context):
        pid = str(os.getpid())        
        dirs_to_check = (
            bpy.app.tempdir,
            os.path.dirname(bpy.app.tempdir),
            tempfile.gettempdir(),
        )

        for dir_to_check in dirs_to_check:
            # empty or nonexistent
            if not dir_to_check or not os.path.isdir(dir_to_check):
                continue

            for file in os.listdir(dir_to_check):
                if file.endswith('_autosave.blend') and pid in file:
                    mtime = os.path.getmtime(os.path.join(dir_to_check, file))
                    mtime = datetime.fromtimestamp(mtime)
                    return (datetime.now() - mtime).total_seconds()

        return None

    def draw(self, context):
        layout = self.layout

        delta = self._get_matching_autosave_file_timestamp(context)
        if delta:
            if delta < 60:
                autosave_label = 'less than a minute ago'
            elif delta < 120:
                autosave_label = '1 minute ago'
            else:
                autosave_label = f'{round(delta // 60)} minutes ago'

            icon = 'ERROR' if (delta // 60) > context.preferences.filepaths.auto_save_time else 'INFO'
            layout.label(text=f'Autosaved {autosave_label}', icon=icon)
        else:
            layout.label(text='No autosave during this session', icon='INFO')

        layout.separator()
        layout.label(text='Modal operators')

        box = layout.box()

        active_operators = set()
        for active_op in context.window.modal_operators:
            active_operators.add(active_op.name)
            if active_op.name in modal_operators:
                continue

            try:
                filepath = inspect.getsourcefile(active_op.__class__)
            except (OSError, TypeError) as e:
                filepath = 'unknown'

            module = active_op.__class__.__module__

            modal_operators[active_op.name] = {
                'filepath': filepath,
                'module': module,
            }
            
        
        for op_name, op_data in modal_operators.items():
            filepath = op_data['filepath']
            module = op_data['module']

            row = box.row(align=True)
            row.label(text=f'{op_name} ({module})', icon='RADIOBUT_ON' if op_name in active_operators else 'RADIOBUT_OFF')

            if filepath != 'unknown':
                op = row.operator(OpenFileInEditor.bl_idname, text='', icon='FILE_TEXT')
                op.filepath = filepath

                op = row.operator(OpenFileDirectory.bl_idname, text='', icon='FILE_FOLDER')
                op.filepath = filepath

            op = row.operator(RemoveModalOperator.bl_idname, text='', icon='X')
            op.name = op_name

        if not modal_operators:
            box.label(text='No (active) modal operators to display', icon='RADIOBUT_OFF')


cls_to_register = [
    OpenFileInEditor,
    RemoveModalOperator,
    OpenFileDirectory,
    ModalOperatorPanel,
]


def register():
    for cls in cls_to_register:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(cls_to_register):
        bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    register()