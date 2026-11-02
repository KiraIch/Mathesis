namespace MathesisPilot
theorem lean_nat_add_right_cancel : ∀ (a b c : Nat), a + c = b + c → a = b := by
  intro a
  intro b
  intro c
  intro h
  exact Nat.add_right_cancel h
end MathesisPilot
