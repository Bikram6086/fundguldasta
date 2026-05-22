from engine.precompute import run_precomputation
for h, c in [(5, 14), (10, 16), (15, 16)]:
    print(f'Computing {h}yr horizon...', flush=True)
    run_precomputation(h, c)
    print(f'{h}yr done', flush=True)
print('All recomputes complete')
