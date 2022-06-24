import lg_imgui as imgui


ctx = imgui.create_context()
io = imgui.get_io()

# Build atlas
io.fonts.build()

for n in range(20):
    print(f"NewFrame {n}")
    io.display_size = imgui.ImVec2(1920, 1080)
    iod = io.display_size
    io.delta_time = 1.0 / 60.0

    imgui.new_frame()

    f = imgui.BoxedFloat(0.0)
    imgui.text("Hello, world")
    imgui.slider_float("float", f, 0.0, 1.0)
    imgui.show_demo_window(None)

    imgui.render()

imgui.destroy_context()
