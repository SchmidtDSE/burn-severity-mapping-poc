import sketchingpy

sketch = sketchingpy.Sketch2D(500, 500)

sketch.clear('#F0F0F0')

sketch.set_fill('#C0C0C0')
sketch.set_stroke('#000000')
sketch.draw_ellipse(250, 250, 20, 20)

sketch.show()