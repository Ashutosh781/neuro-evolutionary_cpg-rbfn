from torch import nn, tanh, zeros, cat, relu

class FC(nn.Module):
  """Fully Connected Feed Forward Network for controlling the robot"""

  def __init__(self, in_size, hid1_size, hid2_size, out_size):
    super(FC, self).__init__()
    self.in_size = in_size
    self.hid1_size = hid1_size
    self.hid2_size = hid2_size
    self.out_size = out_size

    self.hid1 = nn.Linear(self.in_size, self.hid1_size)
    self.hid2 = nn.Linear(self.hid1_size, self.hid2_size)
    self.out = nn.Linear(self.hid2_size, self.out_size)

    self.dim = (self.in_size * self.hid1_size  * self.hid2_size * self.out_size) + (self.hid1_size  + self.hid2_size + self.out_size)
    self.params = zeros(self.dim)

    #Initialize weights and biases
    nn.init.xavier_uniform_(self.hid1.weight)
    nn.init.zeros_(self.hid1.bias)
    nn.init.xavier_uniform_(self.hid2.weight)
    nn.init.zeros_(self.hid2.bias)
    nn.init.xavier_uniform_(self.out.weight)
    nn.init.zeros_(self.out.bias)

  def forward(self, x):
    z = relu(self.hid1(x))
    z = relu(self.hid2(z))
    z = tanh(self.out(z))
    return z

  def get_params(self):
    hid1_weights = nn.utils.parameters_to_vector(self.hid1.weight)
    hid1_bias = nn.utils.parameters_to_vector(self.hid1.bias)
    hid2_weights = nn.utils.parameters_to_vector(self.hid2.weight)
    hid2_bias = nn.utils.parameters_to_vector(self.hid2.bias)
    out_weights = nn.utils.parameters_to_vector(self.out.weight)
    out_bias = nn.utils.parameters_to_vector(self.out.bias)
    return cat((hid1_weights, hid1_bias, hid2_weights, hid2_bias, out_weights, out_bias), dim=0)

  def set_params(self, params):
    in_to_hid1 =self.in_size * self.hid1_size
    in_to_hid1_bias = in_to_hid1 + self.hid1_size

    hid1_to_hid2 = self.hid1_size * self.hid2_size
    hid1_to_hid2_bias = hid1_to_hid2 + self.hid2_size

    hid2_to_out = self.hid2_size * self.out_size
    hid2_to_out_bias = hid2_to_out + self.out_size

    self.hid1.weight.data = params[0 : in_to_hid1].reshape((self.hid1_size, self.in_size))
    self.hid1.bias.data = params[in_to_hid1 : in_to_hid1_bias]

    self.hid2.weight.data = params[in_to_hid1_bias : in_to_hid1_bias + hid1_to_hid2].reshape((self.hid2_size, self.hid1_size))
    self.hid2.bias.data = params[in_to_hid1_bias + hid1_to_hid2 : in_to_hid1_bias + hid1_to_hid2_bias]

    self.out.weight.data = params[in_to_hid1_bias + hid1_to_hid2_bias : in_to_hid1_bias + hid1_to_hid2_bias + hid2_to_out].reshape((self.out_size, self.hid2_size))
    self.out.bias.data = params[in_to_hid1_bias + hid1_to_hid2_bias + hid2_to_out : in_to_hid1_bias + hid1_to_hid2_bias + hid2_to_out_bias]