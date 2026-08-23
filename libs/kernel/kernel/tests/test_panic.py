from kernel.panic import PanicProtocol


def test_panic_invokes_all_callbacks_and_trips():
    panic = PanicProtocol()
    calls = []
    panic.register(lambda: calls.append("gateway_a"))
    panic.register(lambda: calls.append("gateway_b"))

    elapsed = panic.trigger()

    assert calls == ["gateway_a", "gateway_b"]
    assert panic.tripped is True
    assert elapsed < 5.0
