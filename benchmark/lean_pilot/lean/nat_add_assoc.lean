namespace MathesisPilot
theorem lean_nat_add_assoc : ∀ (a b c : Nat), (a + b) + c = a + (b + c) := by
  intro a
  intro b
  intro c
  exact Nat.add_assoc a b c
end MathesisPilot
