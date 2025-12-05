import tkinter as tk

# ----------------------------------------------------------------------
# SHARED UI CONSTANTS
# ----------------------------------------------------------------------
# Centralized colors and fonts for future theming updates
COLORS = {
    "bg_dark": "#111111",
    "bg_panel": "#222222",
    "bg_tooltip": "#333333",
    "text_main": "#00FF00",
    "text_warn": "#FF0000",
    "text_info": "#00FFFF",
    "text_gold": "#FFD700",
    "text_dim": "#AAAAAA",
    "text_white": "#FFFFFF"
}

FONTS = {
    "header": ("Courier", 24, "bold"),
    "sub_header": ("Courier", 16, "bold"),
    "body": ("Courier", 12),
    "small": ("Courier", 10),
    "tiny": ("Courier", 8)
}

# ----------------------------------------------------------------------
# RICH TOOLTIP
# ----------------------------------------------------------------------
class ToolTip:
    """
    A unified ToolTip class that supports string content or lists of (text, color) tuples.
    Supports both Vertical (default) and Horizontal layouts for list items.
    """
    def __init__(self, widget, content_func, horizontal=False):
        self.widget = widget
        self.content_func = content_func
        self.horizontal = horizontal
        self.tip_window = None

    def showtip(self, content):
        """
        Display text or structured data in a tooltip window.
        """
        if self.tip_window or not content: return
        
        # Calculate position
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        
        # Container Frame
        f = tk.Frame(tw, background=COLORS["bg_tooltip"], relief="solid", borderwidth=1)
        f.pack()

        # Content Rendering
        if isinstance(content, str):
            # Simple String
            tk.Label(
                f, text=content, justify="left", 
                background=COLORS["bg_tooltip"], foreground=COLORS["text_white"], 
                font=FONTS["small"]
            ).pack(ipadx=5, ipady=3)
            
        elif isinstance(content, list):
            # List of (Text, Color)
            if self.horizontal:
                # Horizontal Flow (e.g., Tags: [Tech], [Science])
                row = tk.Frame(f, bg=COLORS["bg_tooltip"])
                row.pack(ipadx=5, ipady=3)
                for text, color in content:
                    tk.Label(
                        row, text=text, fg=color, 
                        bg=COLORS["bg_tooltip"], font=FONTS["small"]
                    ).pack(side="left")
            else:
                # Vertical Stack (e.g., Requirements list)
                for text, color in content:
                    tk.Label(
                        f, text=text, fg=color, 
                        bg=COLORS["bg_tooltip"], font=FONTS["small"], 
                        justify="left"
                    ).pack(anchor="w", padx=5)

    def hidetip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw: tw.destroy()

def create_tooltip(widget, content_or_func, horizontal=False):
    """
    Public factory to attach a tooltip to a widget.
    
    Args:
        widget: The tkinter widget to bind to.
        content_or_func: Either a string, a list, or a function returning one.
        horizontal (bool): If True, list items are packed horizontally (good for tags).
    """
    def enter(event):
        content = content_or_func() if callable(content_or_func) else content_or_func
        tooltip.showtip(content)
        
    def leave(event):
        tooltip.hidetip()
        
    tooltip = ToolTip(widget, content_or_func, horizontal=horizontal)
    widget.bind('<Enter>', enter)
    widget.bind('<Leave>', leave)