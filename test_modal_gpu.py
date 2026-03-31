import modal
print(dir(modal))
try:
    print(modal.gpu)
except Exception as e:
    print("No modal.gpu", e)
