# Home Assistant support for Xiaomi Whale Smart Toilet Cover

This is for Xiaomi Mijia Whale Smart Toilet Cover (xjx.toilet.pro).

## Install:
- Install it with [HACS](https://hacs.xyz/)
- Add the configuration to `configuration.yaml`, example:

```yaml
toiletlid:
  - platform: xjx_toilet_pro
    host: 192.168.0.105
    token: !secret xjx_toilet_pro_token
    name: 'Xiaomi Whale Smart Toilet Cover'
```

Services described in the `services.yaml`.

## Requirement

You need to install also [Toiletlid](https://github.com/tykarol/home-assistant-toiletlid).
