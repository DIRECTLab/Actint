from numpy import random as r

VISIBLE: bool = True
FIRST_BACK: bool = False

def visible(visible_chance: float, invisible_chance: float, stay_visible_chance: float) -> bool:
  """
  This function uses global state to determine if an object is "there" based on visibility chances. It works on the defaults that if the object is visible it has a 95% chance to remain visible, and if it is invisible it has an 80% chance to remain invisible. The first time an object becomes visible again it has an 80% chance to stay visible instead of the normal 95%.
  
  :param visible_chance: The chance that an object that is currently visible remains visible.
  :type visible_chance: float
  :param invisible_chance: The chance that an object that is currently invisible remains invisible.
  :type invisible_chance: float
  :param stay_visible_chance: The chance that an object that has just become visible remains visible.
  :type stay_visible_chance: float
  :return: Whether the object is considered "there" (visible).
  :rtype: bool
  """
  global VISIBLE
  global FIRST_BACK
  if not VISIBLE:
    if r.random() > invisible_chance:
      VISIBLE = True
      FIRST_BACK = True
      return False
    else:
      return False
  elif VISIBLE and FIRST_BACK:
    if r.random() > stay_visible_chance:
      VISIBLE = False
      FIRST_BACK = False
      return True
    else:
      VISIBLE = True
      FIRST_BACK = False
      return True
  elif VISIBLE and not FIRST_BACK:
    if r.random() > visible_chance:
      VISIBLE = False
      FIRST_BACK = False
      return True
    else:
      return True